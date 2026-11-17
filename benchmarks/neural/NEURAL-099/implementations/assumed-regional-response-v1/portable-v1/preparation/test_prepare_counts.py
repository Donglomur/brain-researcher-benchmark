"""Generated coordinator checks; no source data, native imports or models."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

import count_oracle
import prepare_counts
import stream_counts


def fixture():
    asset = {'asset_id':'fixture-asset','eligible_unit_row_ordinals':[0,2,3],
        'source_unit_row_values':[[7,'MGv','good'],[8,' ','mua'],[9,'MGv','mua'],[10,'MGd','mua']],
        'spike_times':{'shape':[6]}}
    timing = {'rows':[{'row_ordinal':0,'source_trial_id':15,'start_time':1.,'stop_time':1.0001},
                     {'row_ordinal':1,'source_trial_id':38,'start_time':1.7,'stop_time':1.7001}]}
    records = []
    for row,start,values in [(0,0,[.9,1.,1.001]),(2,4,[]),(3,4,[1.699,1.7])]:
        cluster,region,quality=asset['source_unit_row_values'][row]
        records.append({'asset_id':asset['asset_id'],'source_unit_row':row,'cluster_id':cluster,
            'region':region,'quality':quality,'declared_spike_count':len(values),
            'source_global_start':start,'source_global_stop':start+len(values),
            'chunks':iter([{'source_start':0,'spikes':values}]) if values else iter([])})
    return asset,timing,records


class CoordinatorTests(unittest.TestCase):
    def run_fixture(self, records_transform=None, oracle=count_oracle):
        asset,timing,records=fixture()
        if records_transform: records=records_transform(records)
        return prepare_counts.prepare_asset_counts(asset,timing,'fixture-animal',iter(records),
            production=stream_counts,oracle=oracle)

    def test_one_shot_reader_is_replayed_for_independent_algorithms(self):
        rows,audit=self.run_fixture()
        self.assertEqual([r['case_id'] for r in rows],
            ['fixture-asset:0:MGd','fixture-asset:0:MGv','fixture-asset:1:MGd','fixture-asset:1:MGv'])
        self.assertEqual(audit['selected_events_consumed'],5)
        self.assertEqual(audit['cluster_bins_compared'],1200)
        self.assertEqual(audit['regional_bins_compared'],800)
        self.assertEqual(rows[1]['response_counts'][0:2],[1,1])
        self.assertEqual(rows[2]['response_counts'][0],1)

    def test_empty_cluster_stays_in_region_denominator(self):
        rows,audit=self.run_fixture()
        self.assertEqual(audit['region_denominators'],{'MGd':1,'MGv':2})
        rate=count_oracle.nominal_rates([rows[1]['response_counts']],audit['region_denominators']['MGv'])
        self.assertEqual(rate[0][:2],[500.,500.])
        self.assertEqual(audit['cluster_event_audit'][1]['source_spikes_consumed'],0)

    def test_missing_replayed_reordered_or_relabelled_cluster_refuses(self):
        transforms=[lambda x:x[:-1],lambda x:x[:1]+x,lambda x:list(reversed(x)),
                    lambda x:[dict(x[0],region='MGd')]+x[1:]]
        for transform in transforms:
            with self.subTest(transform=transform),self.assertRaises(ValueError):
                self.run_fixture(transform)

    def test_independent_cluster_error_stops_before_aggregate(self):
        def wrong(*args,**kwargs):
            result=count_oracle.count_cluster(*args,**kwargs)
            result['response_counts'][0][0]+=1
            return result
        with self.assertRaisesRegex(ValueError,'Independent count mismatch'):
            self.run_fixture(oracle=SimpleNamespace(count_cluster=wrong))

    def test_incomplete_or_unbounded_payload_refuses_before_counting(self):
        for transform in [lambda x:[dict(x[0],chunks=iter([]))]+x[1:],
                          lambda x:[dict(x[0],declared_spike_count=999)]+x[1:]]:
            with self.assertRaises(ValueError): self.run_fixture(transform)

    def test_case_identity_uses_source_id_and_frozen_region_count(self):
        asset,timing,_=fixture()
        cases=prepare_counts.asset_cases(asset,timing,'fixture-animal')
        self.assertEqual(cases[0]['source_trial_id'],15)
        self.assertEqual(cases[2]['source_trial_id'],38)
        self.assertEqual([c['source_cluster_count'] for c in cases],[1,2,1,2])
        self.assertEqual(cases[2]['trial_start_seconds'],1.7)


if __name__=='__main__': unittest.main()
