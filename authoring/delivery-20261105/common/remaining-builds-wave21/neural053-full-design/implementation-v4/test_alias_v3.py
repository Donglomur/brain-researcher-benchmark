"""One narrowly scoped invented alias-to-packet composition control; no random key."""
import json
from unittest.mock import patch
from cohort import Profile, partition_images, make_case_metadata, make_aliaser
from frontdoor import _fresh_aliaser
from io_support import canonical_bytes


def main():
    profile=Profile(classes=2,sessions=1,runs=1,engineering=True)
    images={1000+c*12+j:c for c in range(1,3) for j in range(12)}
    query,_=partition_images(images,profile)
    rows=[{"person":person,"epoch_index":i,"session":1,"run":1,"image_id":image,"category_id":category,
           "partition":"query" if image in query else "training"}
          for person in profile.people for i,(image,category) in enumerate(sorted(images.items()))]
    secret=b"i"*32  # Explicit invented bytes; never an existing secret.
    assert len(secret)==32
    with patch('secrets.token_bytes',return_value=secret) as generator:
        alias=_fresh_aliaser()
    generator.assert_called_once_with(32)
    expected=make_aliaser(secret)
    for domain in ('row','person','image','case'):
        value=alias('paired/f0/neural',domain,'invented')
        assert len(value)==32 and value==expected('paired/f0/neural',domain,'invented')
        assert value==alias('paired/f0/neural',domain,'invented')
        assert value!=alias('different/f0/neural',domain,'invented')
    packet,support,train,held=make_case_metadata(rows,profile.people[0],'paired/f0/neural',alias,profile)
    assert len(train)==60 and len(held)==4 and len(packet['groups'])==60
    assert all(len(row[name])==32 for row in packet['groups'] for name in ('training_id','person_group','image_group'))
    size=len(canonical_bytes(rows))+len(canonical_bytes(packet))+len(canonical_bytes(support))
    assert size<=32768
    print(json.dumps({'schema':'neural053_alias_composition_control_v3','controls_passed':1,'natural_exit_expected':0,
                      'invented_rows':96,'training_rows':60,'query_rows':4,'serialized_input_output_bytes':size,
                      'conservative_fixture_debit_bytes':32768,'real_secret_generated':False,
                      'authentic_data_or_scientific_execution':False}))


if __name__=='__main__':main()
