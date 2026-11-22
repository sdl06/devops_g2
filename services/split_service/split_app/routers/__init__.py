"""Register the Split Service routes on a shared Flask blueprint."""

from .common import api as api
from . import allocations as allocations
from . import checkout as checkout
from . import participants as participants
