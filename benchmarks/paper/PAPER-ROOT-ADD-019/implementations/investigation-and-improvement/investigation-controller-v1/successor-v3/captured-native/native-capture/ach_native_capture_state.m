classdef ach_native_capture_state < handle
    % Reference semantics retain every allocation debit through exceptions.
    % This is accounting state, never a scientific estimator/model.
    properties
        cfg
        directory
        limits
        files = 0
        bytes = 0
        nodes = 0
        snapshots = 0
        cache_path = ''
        cache_reserved = 0
        root_returned = false
        finished = false
        records = {}
    end
    methods
        function obj=ach_native_capture_state(cfg,directory,limits)
            obj.cfg=cfg;obj.directory=directory;obj.limits=limits;
        end
    end
end
