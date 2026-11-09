"""Disjoint actual source-owned endpoint collectors over the fixed typed layers."""
from ach_resource_endpoints import Endpoints
from n079_common import require, fields, identity


class RoleEndpoints(Endpoints):
    def __init__(self, context, selection):
        fields(selection, ('roles', 'selection_pin'))
        require(set(selection['roles']) == set(context.profile['endpoint_limits']), 'complete endpoint owner roster')
        require(context.admission['receipts']['custody_receipt']['n079_endpoint_selection_pin'] ==
                identity(selection, context.encoding_limits), 'independent exact endpoint/source owner selection')
        owner = 'finalizer' if context.role == 'finalizer' else 'collector'
        super().__init__(context.profile, owner)
        self.values = {k: v for k, v in self.values.items() if selection['roles'][k] == context.role}
        require(set(self.values) == {k for k, role in selection['roles'].items() if role == context.role},
                'actual role matches typed independent endpoint owner class')
        self.role, self.selection_pin = context.role, selection['selection_pin']

    def closed_record(self):
        return {'role': self.role, 'selection_pin': self.selection_pin, 'counters': self.snapshot(closed=True),
                'scope': 'owned positive-return application/framed/pipe layer counters, never a unique all-network total'}
