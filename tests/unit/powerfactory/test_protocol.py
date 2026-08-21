from pathlib import Path

from gis2dgs.powerfactory import PowerFactoryClient


class FakePowerFactoryClient:
    def import_dgs(self, dgs_path: Path) -> None:
        self.path = dgs_path

    def run_load_flow(self) -> bool:
        return True


def accepts_client(client: PowerFactoryClient) -> bool:
    return client.run_load_flow()


def test_protocol_can_be_implemented_without_inheriting() -> None:
    assert accepts_client(FakePowerFactoryClient()) is True
