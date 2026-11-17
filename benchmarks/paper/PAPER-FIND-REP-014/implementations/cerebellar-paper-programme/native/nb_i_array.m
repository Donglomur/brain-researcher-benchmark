function [desc,budget]=nb_i_array(root,name,value,shape,budget)
% Primitive C-order NPY1 writer. No object, pickle or complex representation.
if ~isreal(value)||~(isnumeric(value)||islogical(value)),error('Primitive numeric source only');end
shape=double(shape(:)');if isempty(shape)||any(~isfinite(shape)|shape<0|shape~=fix(shape))||prod(shape)~=numel(value),error('Exact full array shape');end
if numel(value)>budget.limits.max_native_elements,error('Complete array element cap; never truncate');end
if islogical(value),dtype='|i1';precision='int8';value=int8(value);width=1;
elseif isa(value,'double'),dtype='<f8';precision='double';width=8;
elseif isa(value,'single'),dtype='<f4';precision='single';width=4;
elseif isinteger(value)
    if isa(value,'uint64')&&any(value(:)>uint64(intmax('int64'))),error('Unsigned source integer outside exact signed64');end
    dtype='<i8';precision='int64';value=int64(value);width=8;
else,error('Unsupported primitive class');end
parts=arrayfun(@(x)sprintf('%.0f',x),shape,'UniformOutput',false);
hdr=sprintf('{''descr'': ''%s'', ''fortran_order'': False, ''shape'': (%s,), }',dtype,strjoin(parts,', '));
pad=mod(16-mod(10+numel(hdr)+1,16),16);header=uint8([hdr repmat(' ',1,pad) char(10)]);
if numel(header)>65535,error('NPY1 header cap');end
extent=10+numel(header)+numel(value)*width;
[path,budget]=nb_i_reserve(root,name,extent,budget);
fid=fopen(path,'wb','ieee-le');if fid<0,error('Fresh array open');end
try
    n=fwrite(fid,uint8([147 double('NUMPY') 1 0]),'uint8');if n~=8,error('NPY prefix short write');end
    n=fwrite(fid,uint16(numel(header)),'uint16');if n~=1,error('NPY header length short write');end
    n=fwrite(fid,header,'uint8');if n~=numel(header),error('NPY header short write');end
    % MATLAB column-major to declared C order. Preserve all axis lengths,
    % including zero/singleton axes; shape is supplied explicitly above.
    if numel(shape)>1,value=permute(reshape(value,shape),numel(shape):-1:1);end
    n=fwrite(fid,value(:),precision);if n~=numel(value)||ftell(fid)~=extent,error('NPY complete extent');end
    [message,err]=ferror(fid);if err,error('Array write error: %s',message);end
    status=fclose(fid);fid=-1;if status~=0,error('Array close failed');end
catch primary
    if fid>=0
        try,status=fclose(fid);if status~=0,error('Array cleanup close failed');end
        catch close_error,primary=addCause(primary,close_error);end
    end
    rethrow(primary)
end
[digest,nread]=nb_i_hash(path);budget.hash_read_bytes=budget.hash_read_bytes+nread;
desc=struct('path',name,'bytes',extent,'sha256',digest,'shape',{num2cell(shape)},'dtype',dtype);
budget.outputs{end+1}=desc;
end
