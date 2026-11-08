function [path,budget]=nb_i_reserve(root,name,extent,budget)
if ~ischar(name)||isempty(regexp(name,'^[A-Za-z0-9_-]+[.](npy|json)$','once')),error('Flat owned output leaf');end
if extent>budget.limits.max_file_bytes||budget.files+1>budget.limits.max_files||budget.bytes+extent>budget.limits.max_output_bytes,error('Whole output budget exceeded; never crop');end
budget.files=budget.files+1;budget.bytes=budget.bytes+extent;
path=fullfile(root,name);reserved=javaObject('java.io.File',path);
if ~reserved.createNewFile(),error('Fresh exclusive native output leaf required');end
% The trusted process exclusively owns this isolated output directory. The
% outer engine admits bodies only after natural producer close and capture.
end
