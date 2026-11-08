function a=h_read_npy(root,descriptor)
% Inert C-order training NPY v1 reader; native Fortran exports use another ABI.
% No eval, pickle, native object or path traversal.
assert(isstruct(descriptor) && isscalar(descriptor) && isequal(sort(fieldnames(descriptor)),sort({'path';'bytes';'sha256';'shape';'dtype'})),'H:NPY','Exact five-field training descriptor');
rel=descriptor.path;assert(ischar(rel) && ~isempty(rel) && rel(1)~='/' && ~contains(rel,'\') && isempty(regexp(rel,'(^|/)\.\.?(/|$)','once')),'H:Path','Relative input artifact required');
path=fullfile(root,rel);info=dir(path);assert(numel(info)==1 && ~info.isdir && info.bytes==descriptor.bytes,'H:Input','Exact inert input extent');
assert(strcmp(h_io('sha',path),descriptor.sha256),'H:Pin','Input array SHA256 mismatch');
fid=fopen(path,'r','ieee-le');assert(fid~=-1,'H:IO','Input open');cleanup=onCleanup(@()fclose(fid));
magic=fread(fid,8,'*uint8')';assert(isequal(magic,[147 uint8('NUMPY') 1 0]),'H:NPY','Only NPY v1 supported');
n=fread(fid,1,'uint16');assert(isscalar(n) && n>0 && n<=4096,'H:NPY','Bounded header');
header=char(fread(fid,n,'*uint8')');assert(numel(header)==n && header(end)==newline,'H:NPY','Complete inert header');
% Entire-header grammar excludes executable values, object dtypes and extras.
tokens=regexp(header,'^\{''descr'': ''(<f8|<i8|\|u1)'', ''fortran_order'': (True|False), ''shape'': \(([0-9, ]*)\),? \} *\n$','tokens','once');
assert(~isempty(tokens),'H:NPY','Canonical inert header grammar');
dtype=tokens{1};fortran=strcmp(tokens{2},'True');dims=regexp(tokens{3},'\d+','match');shape=cellfun(@str2double,dims);
assert(strcmp(dtype,descriptor.dtype) && isequal(double(descriptor.shape(:))',shape) && ~fortran,'H:NPY','Header descriptor mismatch');
count=prod(shape);width=8;precision='double';
if strcmp(dtype,'<i8'),precision='int64';elseif strcmp(dtype,'|u1'),precision='uint8';width=1;end
assert(10+n+width*count==info.bytes,'H:NPY','Exact NPY payload extent');
data=fread(fid,count,['*' precision]);assert(numel(data)==count,'H:IO','Complete NPY payload');
assert(isempty(fread(fid,1,'uint8')),'H:NPY','No trailing bytes');
if isempty(shape),a=data(1);elseif numel(shape)==1,a=reshape(data,[],1);
elseif fortran,a=reshape(data,shape);
else,a=permute(reshape(data,fliplr(shape)),numel(shape):-1:1);end
if strcmp(dtype,'|u1'),assert(all(a(:)==0 | a(:)==1),'H:Mask','Binary mask only');end
end
