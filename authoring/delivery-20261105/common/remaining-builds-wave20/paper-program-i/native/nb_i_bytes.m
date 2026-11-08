function [desc,budget]=nb_i_bytes(root,name,raw,budget)
if ~isa(raw,'uint8'),error('Exact UTF8 byte vector');end
[path,budget]=nb_i_reserve(root,name,numel(raw),budget);
fid=fopen(path,'wb');if fid<0,error('Fresh metadata open');end
try
    n=fwrite(fid,raw,'uint8');if n~=numel(raw),error('Metadata short write');end
    [message,err]=ferror(fid);if err,error('Metadata write error: %s',message);end
    status=fclose(fid);fid=-1;if status~=0,error('Metadata close failed');end
catch primary
    if fid>=0
        try,status=fclose(fid);if status~=0,error('Metadata cleanup close failed');end
        catch close_error,primary=addCause(primary,close_error);end
    end
    rethrow(primary)
end
[digest,nread]=nb_i_hash(path);budget.hash_read_bytes=budget.hash_read_bytes+nread;
desc=struct('path',name,'bytes',numel(raw),'sha256',digest);
end
