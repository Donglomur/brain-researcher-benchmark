function [out,budget]=nb_i_typed(v,root,prefix,budget,depth)
% Private complete registration tree; no inferred orientation/identity.
budget.nodes=budget.nodes+1;if budget.nodes>budget.limits.max_collection_items||depth>64,error('Full registration node/depth cap');end
out=struct('source_class',class(v),'shape',size(v));
if isnumeric(v)||islogical(v)
    out.kind='array';[out.array,budget]=nb_i_array(root,[prefix '.npy'],v,size(v),budget);
elseif ischar(v),out.kind='text';out.value=v;
elseif isstring(v)||iscategorical(v),out.kind='text_array';out.values=cellstr(string(v));out.missing=num2cell(ismissing(v));
elseif iscell(v)
    out.kind='cell';out.items=cell(size(v));
    for k=1:numel(v),[out.items{k},budget]=nb_i_typed(v{k},root,sprintf('%s_c%d',prefix,k),budget,depth+1);end
elseif isstruct(v)
    out.kind='struct';names=fieldnames(v);out.items=cell(1,numel(v));
    for k=1:numel(v)
        item=cell(1,numel(names));for j=1:numel(names),[node,budget]=nb_i_typed(v(k).(names{j}),root,sprintf('%s_s%d_f%d',prefix,k,j),budget,depth+1);item{j}=struct('name',names{j},'value',node);end
        out.items{k}=item;
    end
elseif istable(v)
    out.kind='table';names=v.Properties.VariableNames;out.columns=cell(1,numel(names));
    for j=1:numel(names),[node,budget]=nb_i_typed(v.(names{j}),root,sprintf('%s_t%d',prefix,j),budget,depth+1);out.columns{j}=struct('name',names{j},'value',node);end
else,error('Unsupported full registration class');end
end
