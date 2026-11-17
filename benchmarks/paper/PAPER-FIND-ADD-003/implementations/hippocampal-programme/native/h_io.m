function out = h_io(action, varargin)
% Private trusted-operator I/O. No candidate MAT files or MATLAB objects.
switch action
    case 'json'
        path=varargin{1}; value=varargin{2};
        assert(~isfile(path) && ~isfolder(path),'H:Fresh','Fresh output required');
        body=unicode2native(jsonencode(value),'UTF-8');
        fid=fopen(path,'w'); assert(fid~=-1,'H:IO','Cannot open output');
        cleanup=onCleanup(@()fclose(fid));
        assert(fwrite(fid,body,'uint8')==numel(body),'H:IO','Short JSON write');
        clear cleanup; info=dir(path);assert(info.bytes==numel(body),'H:IO','JSON extent after close');
        out=struct('path',path,'bytes',numel(body),'sha256',h_io('sha',path));
    case 'sha'
        fid=fopen(varargin{1},'r'); assert(fid~=-1,'H:IO','Cannot open pin operand');
        cleanup=onCleanup(@()fclose(fid)); md=java.security.MessageDigest.getInstance('SHA-256');
        while true
            b=fread(fid,1048576,'*uint8'); if isempty(b),break;end
            md.update(b);
        end
        [msg,code]=ferror(fid); assert(code==0,'H:IO',msg);
        out=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
    case 'array'
        root=varargin{1}; rel=varargin{2}; a=varargin{3}; kind=varargin{4};
        assert(isreal(a),'H:Complex','Complex input is unsupported');
        if strcmp(kind,'<f8'), a=double(a); precision='double'; width=8;
        elseif strcmp(kind,'<i8'), assert(all(isfinite(a(:))) && all(a(:)==fix(a(:))),'H:Integer','Integer array required'); a=int64(a);precision='int64';width=8;
        elseif strcmp(kind,'|u1'), assert(all(a(:)==0 | a(:)==1),'H:Mask','Binary mask required');a=uint8(a);precision='uint8';width=1;
        else,error('H:Dtype','Unsupported dtype');end
        assert(~any(isinf(a(:))),'H:Infinity','Infinite original values are admission failures');
        shape=size(a);
        if numel(varargin)>=5
            shape=varargin{5};assert(isnumeric(shape) && all(shape>=0 & shape==fix(shape)) && prod(shape)==numel(a),'H:Shape','Exact declared inert shape required');
        end
        path=fullfile(root,rel);
        assert(~isfile(path) && ~isfolder(path),'H:Fresh','Fresh array required');
        parent=fileparts(path); if ~isfolder(parent),mkdir(parent);end
        dims=sprintf('%d, ',shape); header=sprintf('{''descr'': ''%s'', ''fortran_order'': True, ''shape'': (%s), }',kind,dims);
        pad=mod(64-mod(10+numel(header)+1,64),64); header=[header repmat(' ',1,pad) newline];
        assert(numel(header)<65536,'H:Header','NPY v1 header limit');
        fid=fopen(path,'w','ieee-le');assert(fid~=-1,'H:IO','Cannot open array');cleanup=onCleanup(@()fclose(fid));
        assert(fwrite(fid,[147 uint8('NUMPY') 1 0],'uint8')==8,'H:IO','Short NPY magic');
        assert(fwrite(fid,numel(header),'uint16')==1,'H:IO','Short header length');
        assert(fwrite(fid,uint8(header),'uint8')==numel(header),'H:IO','Short header');
        % MATLAB column-major bytes are explicitly declared Fortran-order.
        count=numel(a); block=131072;
        for start=1:block:count
            stop=min(count,start+block-1);
            assert(fwrite(fid,a(start:stop),precision)==stop-start+1,'H:IO','Short array body');
        end
        clear cleanup; expected=10+numel(header)+count*width;info=dir(path);assert(info.bytes==expected,'H:IO','NPY extent after close');
        out=struct('path',rel,'dtype',kind,'shape',{num2cell(shape)},'fortran_order',true,'bytes',expected,'sha256',h_io('sha',path));
    case 'numeric'
        root=varargin{1};rel=varargin{2};a=varargin{3};
        assert(isnumeric(a) || islogical(a),'H:Numeric','Numeric original required');
        out=h_io('array',root,[rel '.npy'],a,'<f8');
        out.nan_mask=h_io('array',root,[rel '.missing.npy'],isnan(a),'|u1');
        out.original_class=class(a);
    case 'pack'
        % Preserve every ROI metadata field without evaluating opaque objects.
        root=varargin{1};prefix=varargin{2};x=varargin{3};
        if isnumeric(x) || islogical(x)
            out=struct('kind','numeric','value',h_io('numeric',root,prefix,x));
        elseif ischar(x)
            out=struct('kind','char','shape',size(x),'value',{cellstr(x)});
        elseif isstring(x)
            out=struct('kind','string','shape',size(x),'value',{cellstr(x)});
        elseif isdatetime(x)
            out=struct('kind','datetime_text','shape',size(x),'value',{cellstr(string(x))},'timezone',x.TimeZone,'format',x.Format);
        elseif iscell(x)
            values=cell(1,numel(x));
            for k=1:numel(x),values{k}=h_io('pack',root,sprintf('%s/c%06d',prefix,k),x{k});end
            out=struct('kind','cell','shape',size(x),'values',{values});
        elseif isstruct(x)
            fields=fieldnames(x);values=cell(numel(x),numel(fields));
            for k=1:numel(x)
                for f=1:numel(fields),values{k,f}=h_io('pack',root,sprintf('%s/s%06d/f%04d',prefix,k,f),x(k).(fields{f}));end
            end
            out=struct('kind','struct','shape',size(x),'fields',{fields},'values',{values});
        else
            error('H:Opaque','Unsupported original class %s; preparation remains incomplete',class(x));
        end
    case 'error'
        e=varargin{1};out=struct('identifier',e.identifier,'message',e.message,'stack',{e.stack});
    otherwise,error('H:Action','Unknown I/O action');
end
end
