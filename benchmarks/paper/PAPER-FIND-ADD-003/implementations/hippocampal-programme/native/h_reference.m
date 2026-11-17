function h_reference(request_path)
% Independent native reference: exact five pinned source functions, 11 calls.
% No replacement fits, NaN-bin shortcuts, cell-count changes or RNG changes.
r=jsondecode(fileread(request_path));
assert(strcmp(r.schema,'h_native_request_v2') && strcmp(r.operation,'reference'),'H:Request','Wrong request');
assert(strcmp(r.output_root,'/output'),'H:Path','Fixed output mount');root=r.output_root;
assert(isfolder(root) && numel(dir(root))==2,'H:Fresh','Empty owned output mount required');
variants={'source_preprocessing','no_smoothing_no_flooring'};
calls=cell(1,11); calls{1}=record(1,'reference_behavior',1,'behavior.mat',0,'no_source_rng_reset');
for v=1:2
    mkdir(fullfile(root,variants{v}));base=1+(v-1)*5;
    calls{base+1}=record(base+1,'reference_sequence',v+1,[variants{v} '/sequence_short.mat'],169,'source_rng_Default');
    calls{base+2}=record(base+2,'reference_sequence',v+1,[variants{v} '/sequence_long.mat'],247,'source_rng_Default');
    calls{base+3}=record(base+3,'reference_time',v+1,[variants{v} '/time.mat'],0,'source_rng_Default');
    calls{base+4}=record(base+4,'reference_odor',v+1,[variants{v} '/odor.mat'],0,'source_rng_Default');
    calls{base+5}=record(base+5,'reference_information',v+1,[variants{v} '/information.mat'],0,'source_rng_Default');
end
exporter=struct('function','export_values','status','unstarted','output','export-values.json','reason','reference_calls_not_complete');
initial=struct('schema','h_native_call_ledger_v2','calls',{calls},'exporter',exporter,'scientific_qualification',false);
h_io('json',fullfile(root,'call-ledger.initial.json'),initial);
try
    names={'reference_behavior','reference_sequence','reference_time','reference_odor','reference_information','export_values'};
    pins={'3c2e71bc596a0fb2572061ceddfcb6551002a749543298458824aec072c0ded9',...
          'e50b1c6daaf91ff9bfcc9b70645062f3253473055dd07a44a3186c752c7ff0ff',...
          'e8646e51fa9a10d76f6d5bed9cdcc057af8fe9dde0339e61073252449787c1c3',...
          'b2f74d67cf806a759e2cf301af00cec488b97d28049b132a462585fc155be419',...
          '9887f33672340fe62a178cfb78ccf93a9ff1ca34609ca6bd7739e805329c9aaa',...
          'cd062529d9a53c60426a8c97369e13e639484dbc45fb420333911f1f7810628e'};
    addpath('/author');addpath('/author/reference_sources');
    for j=1:numel(names)
        folder='/author/reference_sources';if j==6,folder='/author';end
        expected=fullfile(folder,[names{j} '.m']);
        assert(strcmp(which(names{j}),expected),'H:Shadow','Source function shadowed');
        assert(strcmp(h_io('sha',expected),pins{j}),'H:Pin','Reference source pin mismatch');
    end
    for k=1:11
        c=calls{k};c.status='started';c.started_utc=stamp();
        % A durable started record distinguishes interruption from unstarted.
        h_io('json',fullfile(root,sprintf('call-%02d.started.json',k)),c);
        try
            input=r.originals(c.original_ordinal).path;output=fullfile(root,c.output);
            if k==1
                reference_behavior(input,output);
            else
                switch mod(k-2,5)
                    case 0,reference_sequence(input,output,169);
                    case 1,reference_sequence(input,output,247);
                    case 2,reference_time(input,output);
                    case 3,reference_odor(input,output);
                    case 4,reference_information(input,output);
                end
            end
            assert(isfile(output),'H:Output','Native call returned without output');
            info=dir(output);c.output_bytes=info.bytes;c.output_sha256=h_io('sha',output);c.status='completed';
        catch e
            c.status='failed';c.error=h_io('error',e);
            % Preserve native partial MAT output and the original exception.
            output=fullfile(root,c.output);
            if isfile(output),info=dir(output);c.partial_output_bytes=info.bytes;end
        end
        c.finished_utc=stamp();calls{k}=c;
        h_io('json',fullfile(root,sprintf('call-%02d.json',k)),c);
    end
    if all(cellfun(@(c)strcmp(c.status,'completed'),calls))
        exporter.status='started';exporter.started_utc=stamp();
        h_io('json',fullfile(root,'exporter.started.json'),exporter);
        try
            export_values(root,fullfile(root,'export-values.json'));
            exporter.status='completed';exporter.sha256=h_io('sha',fullfile(root,'export-values.json'));
        catch e,exporter.status='failed';exporter.error=h_io('error',e);end
        exporter.finished_utc=stamp();
    end
catch e
    exporter.reason='orchestration_or_source_admission_failure';exporter.error=h_io('error',e);
end
ledger=struct('schema','h_native_call_ledger_v2','calls',{calls},'exporter',exporter,...
    'scientific_qualification',false,'native_calls_expected',11,'output_slots_expected',56868,...
    'all_calls_completed',all(cellfun(@(c)strcmp(c.status,'completed'),calls)));
h_io('json',fullfile(root,'call-ledger.json'),ledger);
end

function c=record(k,fn,original,path,window,rngpolicy)
c=struct('ordinal',k,'function',fn,'original_ordinal',original,'output',path,'window',window,...
    'rng_policy',rngpolicy,'status','unstarted');
end

function s=stamp()
s=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSS''Z'''));
end
