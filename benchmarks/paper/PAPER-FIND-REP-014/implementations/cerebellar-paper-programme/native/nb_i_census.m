function [out,budget]=nb_i_census(v,budget,depth)
% Complete structural census; numeric payloads stay out of JSON.
budget.nodes=budget.nodes+1;if budget.nodes>budget.limits.max_collection_items||depth>64,error('Complete census node/depth cap; never truncate');end
out=struct('class',class(v),'shape',size(v),'empty',isempty(v));
if isnumeric(v)||islogical(v)
    out.kind='numeric';out.numeric_values_exposed=false;
elseif ischar(v)
    if numel(unicode2native(v(:)','UTF-8'))>budget.limits.max_metadata_bytes,error('Complete source string cap');end
    out.kind='text';out.value=v;
elseif isstring(v)||iscategorical(v)
    out.kind='text_array';out.values=cellstr(string(v));out.missing=num2cell(ismissing(v));
elseif iscell(v)
    out.kind='cell';out.items=cell(size(v));
    for k=1:numel(v),[out.items{k},budget]=nb_i_census(v{k},budget,depth+1);end
elseif isstruct(v)
    out.kind='struct';names=fieldnames(v);out.fields=names;out.items=cell(1,numel(v));
    for k=1:numel(v)
        item=cell(1,numel(names));for j=1:numel(names),[node,budget]=nb_i_census(v(k).(names{j}),budget,depth+1);item{j}=struct('name',names{j},'value',node);end
        out.items{k}=item;
    end
elseif istable(v)
    out.kind='table';names=v.Properties.VariableNames;out.columns=cell(1,numel(names));
    for j=1:numel(names),[node,budget]=nb_i_census(v.(names{j}),budget,depth+1);out.columns{j}=struct('name',names{j},'value',node);end
else,error('Unsupported native census class %s: complete support unavailable',class(v));end
end
