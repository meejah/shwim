from rich.text import Text
from rich.progress import Progress, SpinnerColumn


class WormholeStatus:

    def __init__(self, read_only=False):
        txt = Text(
            "Instant terminal sharing via Magic Wormhole\n"
            "Once connected, we launch "
        )
        txt.append(Text("tty-share", style="bold green"))
        if not read_only:
            txt.append("\nNote: --read-only was not specified!")
        self.progress = Progress(
            SpinnerColumn(spinner_name="circleHalves", finished_text="✅", speed=1),
            "{task.description}",
            ##BarColumn(),
            refresh_per_second=1.0,
        )

        from rich.table import Table
        t = self.layout = Table(show_header=False, show_lines=False, show_edge=True, padding=(0,1,1,1))
        t.add_column(justify="right", width=11)
        t.add_column(justify="left")

        self.magic_code = Text("<creating code>", style="green on black", justify="center")
        self.progress

        t.add_row(Text("ShWiM", style="bold green"), txt)
        t.add_row(Text("Magic Code", style="bold red"), self.magic_code)
        t.add_row(Text("Status"), self.progress)

    def set_code(self, code):
        self.magic_code.plain = code

    def __rich__(self):
        return self.layout
