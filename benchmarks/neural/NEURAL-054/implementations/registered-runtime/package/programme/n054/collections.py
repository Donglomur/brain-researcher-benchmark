"""Bounded immutable Merkle collections: no whole-bank JSON manifest ceiling.
Both leaves and index nodes are capped; arbitrary counts add levels, not bigger
root objects. Logical artifacts and original IDs are never dropped or sampled.
"""
from pathlib import Path
from .common import need, canonical, digest, put, load, relative


class Collections:
    def __init__(self, root, byte_cap=1 << 20, item_cap=256):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        need(byte_cap >= 512 and item_cap >= 2, 'Collection node capacity')
        self.byte_cap = byte_cap; self.item_cap = item_cap

    def _node(self, name, level, ordinal, key, items):
        count = len(items) if key == 'items' else sum(x['count'] for x in items)
        value = {'schema': 'n054_collection_node_v2', 'kind': key, key: items, 'count': count}
        rel = f'{name}/{level:04d}/{ordinal:012d}.json'
        return {'path': rel, **put(self.root / rel, value, self.byte_cap), 'count': count, 'level': level}

    def _level(self, name, level, key, items):
        group = []; ordinal = 0
        for item in items:
            candidate = group + [item]
            value = {'schema': 'n054_collection_node_v2', 'kind': key, key: candidate,
                     'count': len(candidate) if key == 'items' else sum(x['count'] for x in candidate)}
            if group and (len(candidate) > self.item_cap or len(canonical(value)) > self.byte_cap):
                yield self._node(name, level, ordinal, key, group); ordinal += 1; group = [item]
            else: group = candidate
            need(len(canonical({'schema': 'n054_collection_node_v2', 'kind': key, key: group,
                                'count': len(group) if key == 'items' else sum(x['count'] for x in group)})) <= self.byte_cap,
                 'Individual collection item exceeds admitted node size')
        if group: yield self._node(name, level, ordinal, key, group)

    def seal(self, identity, items):
        name = digest(identity); level = 0
        nodes = list(self._level(name, level, 'items', items))
        while len(nodes) > 1:
            level += 1; next_nodes = list(self._level(name, level, 'children', nodes))
            need(len(next_nodes) < len(nodes), 'Index node cannot branch at admitted capacity')
            nodes = next_nodes
        return {'schema': 'n054_immutable_collection_v2', 'identity': identity,
                'node_bytes': self.byte_cap, 'node_items': self.item_cap,
                'count': nodes[0]['count'] if nodes else 0, 'root': nodes[0] if nodes else None}

    def iterate(self, seal):
        need(seal['schema'] == 'n054_immutable_collection_v2', 'Collection schema')
        cap = seal['node_bytes']; need(cap == self.byte_cap and seal['node_items'] == self.item_cap, 'Collection policy')
        def visit(ref):
            relative(ref['path']); node = load(self.root / ref['path'], cap, {k: ref[k] for k in ('bytes', 'sha256')})
            need(node['schema'] == 'n054_collection_node_v2' and node['count'] == ref['count'], 'Collection node count')
            key = node['kind']; need(key in ('items', 'children') and 0 < len(node[key]) <= self.item_cap, 'Node members')
            count = 0
            if key == 'items':
                need(ref['level'] == 0, 'Leaf level')
                for item in node[key]: count += 1; yield item
            else:
                for child in node[key]:
                    need(child['level'] == ref['level'] - 1, 'Acyclic levels')
                    for item in visit(child): count += 1; yield item
            need(count == ref['count'], 'Exact recursive support')
        count = 0
        if seal['root'] is not None:
            for item in visit(seal['root']): count += 1; yield item
        need(count == seal['count'], 'Whole collection support')
