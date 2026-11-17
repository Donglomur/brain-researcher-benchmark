"""Source-owned weighted ExtraTrees with the reviewed counter-RNG contract."""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from ._common import (EstimatorError, FrozenArray, numpy, training, matrix,
                      empty, context, context_dict, finite_number, strict_keys, production_features)


class CounterStream:
    def __init__(self, ctx, tree_index, node_path, role, budget):
        token, condition, view, configuration_index, fit_role = ctx
        values = ['n073-extra-trees-v1', 73002, token, condition, view,
                  configuration_index, fit_role, tree_index, node_path, role]
        self.seed = json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.counter = 0
        self.budget = budget
        budget.charge(len(self.seed), 'rng_seed_preimage')

    def word(self):
        self.budget.tick('sha256_rng_words')
        digest = hashlib.sha256(self.seed + b'|' + str(self.counter).encode('ascii')).digest()
        self.counter += 1
        return int.from_bytes(digest[:8], 'big', signed=False)

    def below(self, bound):
        if type(bound) is not int or not 0 < bound <= 2**64:
            raise EstimatorError('invalid_rng_bound')
        limit = 2**64 - (2**64 % bound)
        while True:
            value = self.word()
            if value < limit:
                return value % bound


def eligible_selection(eligible, declared, ctx, tree_index, path, budget):
    """Primitive exposes the exact no-replacement feature rule for controls."""
    if (type(eligible) not in (list,tuple) or any(type(x) is not int or x<0 for x in eligible)
            or list(eligible) != sorted(set(eligible)) or type(declared) is not int or declared<=0):
        raise EstimatorError('invalid_feature_candidates')
    count=min(declared,len(eligible))
    budget.charge(len(eligible)*8,'feature_candidate_indices')
    if count==len(eligible):
        return tuple(eligible)
    values=list(eligible)
    stream=CounterStream(ctx,tree_index,path,'features',budget)
    for j in range(count):
        k=j+stream.below(len(values)-j)
        values[j],values[k]=values[k],values[j]
    return tuple(sorted(values[:count]))


def exact_threshold(lo,hi,ctx,tree_index,path,feature,budget):
    """Correctly round the specified real convex interpolation to binary64."""
    lo=finite_number(lo,'threshold_lower'); hi=finite_number(hi,'threshold_upper')
    if lo>=hi:
        raise EstimatorError('constant_threshold_feature')
    word=CounterStream(ctx,tree_index,path,'threshold:'+str(feature),budget).word()
    integer=word>>11
    u=Fraction(integer,2**53)
    real=(1-u)*Fraction.from_float(lo)+u*Fraction.from_float(hi)
    threshold=float(real)
    if threshold>=hi:
        threshold=math.nextafter(hi,-math.inf)
    if threshold<lo:
        threshold=lo
    if not math.isfinite(threshold) or not lo<=threshold<hi:
        raise EstimatorError('invalid_rounded_threshold')
    budget.tick('exact_threshold_interpolations')
    return threshold


@dataclass(frozen=True)
class TreeNode:
    feature: int
    threshold: float | None
    left: int
    right: int
    probabilities: tuple
    records: int
    weight: float

    def to_dict(self):
        return {'feature':self.feature,'threshold':self.threshold,'left':self.left,
                'right':self.right,'probabilities':list(self.probabilities),
                'records':self.records,'weight':self.weight}


def _histogram(indices,y,weights,classes,budget):
    budget.charge((len(indices)+2*classes)*8,'node_weight_statistics')
    buckets=[[] for _ in range(classes)]
    for j in indices:
        buckets[y[j]].append(float(weights[j]))
    masses=tuple(math.fsum(values) for values in buckets)
    mass=math.fsum(masses)
    if not math.isfinite(mass) or mass<=0:
        raise EstimatorError('invalid_node_weight')
    p=tuple(x/mass for x in masses)
    gini=1.0-math.fsum(x*x for x in p)
    if gini < -1e-12:
        raise EstimatorError('invalid_weighted_gini')
    budget.tick('node_histogram_rows',len(indices))
    return mass,p,max(gini,0.0)


def _one_tree(X,y,weights,classes,minimum,feature_rule,ctx,tree_index,budget):
    n,d=X.shape
    declared=math.isqrt(d) if feature_rule=='floor_sqrt_d' else d
    budget.charge(n*8,'tree_root_indices')
    nodes=[None]
    stack=[(0,tuple(range(n)),'')]
    while stack:
        index,indices,path=stack.pop()
        budget.tick('tree_nodes_constructed')
        mass,p,parent_gini=_histogram(indices,y,weights,classes,budget)
        budget.charge(64+8*classes,'frozen_tree_node_bound')
        leaf=TreeNode(-1,None,-1,-1,p,len(indices),mass)
        if len(indices)<2*minimum or parent_gini==0.0:
            nodes[index]=leaf
            continue
        lows=[];highs=[];eligible=[]
        budget.charge(d*24,'node_feature_bounds_and_indices')
        for feature in range(d):
            lo=min(float(X[j,feature]) for j in indices)
            hi=max(float(X[j,feature]) for j in indices)
            lows.append(lo);highs.append(hi)
            if lo<hi:
                eligible.append(feature)
        budget.tick('node_feature_values_inspected',len(indices)*d)
        if not eligible:
            nodes[index]=leaf
            continue
        selected=eligible_selection(eligible,declared,ctx,tree_index,path,budget)
        best=None
        for feature in selected:
            threshold=exact_threshold(lows[feature],highs[feature],ctx,tree_index,path,feature,budget)
            budget.charge(len(indices)*8,'split_membership_indices')
            left=tuple(j for j in indices if float(X[j,feature])<=threshold)
            right=tuple(j for j in indices if float(X[j,feature])>threshold)
            budget.tick('split_value_comparisons',len(indices))
            if len(left)<minimum or len(right)<minimum:
                continue
            mass_l,_,gini_l=_histogram(left,y,weights,classes,budget)
            mass_r,_,gini_r=_histogram(right,y,weights,classes,budget)
            gain=parent_gini-(mass_l*gini_l+mass_r*gini_r)/mass
            if not math.isfinite(gain):
                raise EstimatorError('nonfinite_gini_gain')
            if gain>0.0 and (best is None or gain>best[0] or
                            (gain==best[0] and (feature,threshold)<(best[1],best[2]))):
                best=(gain,feature,threshold,left,right)
        if best is None:
            nodes[index]=leaf
            continue
        _,feature,threshold,left,right=best
        left_index=len(nodes);right_index=left_index+1
        nodes.extend([None,None])
        nodes[index]=TreeNode(feature,threshold,left_index,right_index,(),len(indices),mass)
        # Iterative traversal does not impose Python's recursion limit on depth.
        stack.append((right_index,right,path+'R'))
        stack.append((left_index,left,path+'L'))
    return tuple(nodes)


@dataclass(frozen=True)
class ExtraTreesState:
    classes: int
    features: int
    min_samples_leaf: int
    max_features_rule: str
    trees: tuple
    fit_context: tuple
    production_wrapper: bool

    def to_dict(self,budget):
        nodes=sum(len(tree) for tree in self.trees)
        # Conservative bound before producing the numeric JSON metadata graph.
        budget.charge(nodes*(192+32*self.classes)+1024,'tree_json_state_bound')
        return {'schema':'n073_extra_trees_state_v1','classes':self.classes,
                'features':self.features,'min_samples_leaf':self.min_samples_leaf,
                'max_features_rule':self.max_features_rule,
                'context':context_dict(self.fit_context),
                'production_wrapper':self.production_wrapper,
                'trees':[[node.to_dict() for node in tree] for tree in self.trees]}

    @classmethod
    def from_dict(cls,value,budget,*,max_nodes):
        strict_keys(value,['schema','classes','features','min_samples_leaf','max_features_rule',
                           'context','production_wrapper','trees'],'extra_trees_state')
        k=value['classes'];d=value['features'];minimum=value['min_samples_leaf'];raw=value['trees']
        if (value['schema']!='n073_extra_trees_state_v1' or type(k) is not int or not 2<=k<=25
                or type(d) is not int or d<=0 or type(minimum) is not int or minimum<=0
                or value['max_features_rule'] not in ('floor_sqrt_d','all_d')
                or type(value['production_wrapper']) is not bool or type(raw) is not list
                or not 1<=len(raw)<=256 or type(max_nodes) is not int or max_nodes<=0):
            raise EstimatorError('invalid_extra_trees_state')
        if value['production_wrapper'] and (k!=25 or len(raw)!=256 or minimum not in (1,5)):
            raise EstimatorError('invalid_production_tree_grid')
        if any(type(tree) is not list or not tree for tree in raw) or sum(len(tree) for tree in raw)>max_nodes:
            raise EstimatorError('tree_node_extent_limit')
        trees=[]
        for rawtree in raw:
            budget.charge(len(rawtree)*(64+8*k),'decoded_tree_nodes')
            nodes=[]
            for j,x in enumerate(rawtree):
                strict_keys(x,['feature','threshold','left','right','probabilities','records','weight'],'tree_node')
                if (type(x['feature']) is not int or type(x['left']) is not int or type(x['right']) is not int
                        or type(x['records']) is not int or x['records']<=0 or type(x['probabilities']) is not list):
                    raise EstimatorError('invalid_tree_node_fields')
                mass=finite_number(x['weight'],'node_weight',True)
                if mass>1+1e-12:
                    raise EstimatorError('node_weight_above_one')
                if x['feature']==-1:
                    probs=x['probabilities']
                    if x['threshold'] is not None or x['left']!=-1 or x['right']!=-1 or len(probs)!=k:
                        raise EstimatorError('invalid_leaf_fields')
                    if any(type(a) not in (int,float) or not math.isfinite(a) or not 0<=a<=1 for a in probs):
                        raise EstimatorError('invalid_leaf_probability')
                    if abs(math.fsum(probs)-1.0)>1e-12:
                        raise EstimatorError('leaf_probability_sum')
                    nodes.append(TreeNode(-1,None,-1,-1,tuple(float(a) for a in probs),x['records'],mass))
                else:
                    if (not 0<=x['feature']<d or x['probabilities'] or
                            not j<x['left']<len(rawtree) or not j<x['right']<len(rawtree) or x['left']==x['right']):
                        raise EstimatorError('invalid_internal_node_graph')
                    nodes.append(TreeNode(x['feature'],finite_number(x['threshold'],'threshold'),x['left'],x['right'],(),x['records'],mass))
            parent_counts=[0]*len(nodes)
            for node in nodes:
                if node.feature>=0:
                    left=nodes[node.left];right=nodes[node.right]
                    parent_counts[node.left]+=1;parent_counts[node.right]+=1
                    if left.records<minimum or right.records<minimum or left.records+right.records!=node.records:
                        raise EstimatorError('inconsistent_tree_record_counts')
                    if abs((left.weight+right.weight)-node.weight)>1e-12:
                        raise EstimatorError('inconsistent_tree_weight_counts')
            if parent_counts[0]!=0 or any(count!=1 for count in parent_counts[1:]) or abs(nodes[0].weight-1.0)>1e-12:
                raise EstimatorError('tree_unreachable_or_shared_node')
            trees.append(tuple(nodes))
        if value['production_wrapper']:
            class Width:
                shape=(1,d)
            production_features(Width(),value['context'],'extra_trees')
        return cls(k,d,minimum,value['max_features_rule'],tuple(trees),context(value['context']),value['production_wrapper'])


def fit_extra_trees_primitive(X,y,weights,min_samples_leaf,max_features_rule,fit_context,budget,
                              *,classes,trees=256,_production=False):
    n,d=training(X,y,weights,budget,classes);ctx=context(fit_context)
    if type(min_samples_leaf) is not int or min_samples_leaf<=0 or max_features_rule not in ('floor_sqrt_d','all_d'):
        raise EstimatorError('invalid_tree_configuration')
    if type(trees) is not int or not 1<=trees<=256:
        raise EstimatorError('invalid_tree_count')
    forest=[]
    for tree_index in range(trees):
        forest.append(_one_tree(X,y,weights,classes,min_samples_leaf,max_features_rule,ctx,tree_index,budget))
        budget.tick('trees_completed')
    return ExtraTreesState(classes,d,min_samples_leaf,max_features_rule,tuple(forest),ctx,_production)


def fit_extra_trees(X,y,weights,min_samples_leaf,max_features_rule,fit_context,budget):
    matrix(X,budget)
    production_features(X,fit_context,'extra_trees')
    if min_samples_leaf not in (1,5):
        raise EstimatorError('tree_outside_frozen_grid')
    return fit_extra_trees_primitive(X,y,weights,min_samples_leaf,max_features_rule,fit_context,budget,
                                      classes=25,trees=256,_production=True)


def predict_extra_trees(state,X,budget,*,probabilities=False):
    if type(state) is not ExtraTreesState:
        raise EstimatorError('invalid_tree_state_type')
    matrix(X,budget,columns=state.features)
    output=empty((X.shape[0],state.classes),budget,'extra_trees_predictions')
    output.fill(0.0)
    for row in range(X.shape[0]):
        leaves=[]
        budget.charge(len(state.trees)*8,'prediction_leaf_indices')
        for tree in state.trees:
            index=0
            while tree[index].feature>=0:
                node=tree[index]
                budget.tick('prediction_tree_node_visits')
                index=node.left if float(X[row,node.feature])<=node.threshold else node.right
            leaves.append(tree[index].probabilities)
        for k in range(state.classes):
            p=math.fsum(leaf[k] for leaf in leaves)/len(state.trees)
            output[row,k]=p if probabilities else math.log(max(p,1e-12))
        budget.tick('tree_prediction_scores',state.classes)
    return FrozenArray.freeze(output,budget,'tree_predictions')
