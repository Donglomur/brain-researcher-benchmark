function [digest,nread]=nb_i_hash(path)
md=java.security.MessageDigest.getInstance('SHA-256');fid=fopen(path,'rb');if fid<0,error('Native output checksum open');end
nread=0;
try
    while true
        raw=fread(fid,1048576,'*uint8');if isempty(raw),break;end
        nread=nread+numel(raw);md.update(typecast(raw(:),'int8'));
    end
    [message,err]=ferror(fid);if err,error('Checksum read error: %s',message);end
    status=fclose(fid);fid=-1;if status~=0,error('Checksum close failed');end
catch primary
    if fid>=0
        try,status=fclose(fid);if status~=0,error('Checksum cleanup close failed');end
        catch close_error,primary=addCause(primary,close_error);end
    end
    rethrow(primary)
end
bytes=typecast(md.digest(),'uint8');digest=lower(reshape(dec2hex(bytes,2)',1,[]));
end
