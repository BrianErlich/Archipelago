from worlds.LauncherComponents import Component, Type, components, launch


def run_client(*args: str) -> None:
    from .client import launch as launch_bejeweled3_client
    launch(launch_bejeweled3_client, name="Bejeweled 3 Client", args=args)


components.append(
    Component(
        "Bejeweled 3 Client",
        func=run_client,
        game_name="Bejeweled 3",
        component_type=Type.CLIENT,
        supports_uri=True,
    )
)
