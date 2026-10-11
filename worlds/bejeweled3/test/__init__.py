from test.bases import WorldTestBase

from ..world import Bejeweled3World


class Bejeweled3TestBase(WorldTestBase):
    game = "Bejeweled 3"
    world: Bejeweled3World
