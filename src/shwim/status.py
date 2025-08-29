from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.console import Console
from rich.layout import Layout, Align
from rich.padding import Padding
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn


class WormholeStatus:

    def __init__(self):
        txt = Text(
            "Instant terminal sharing via Magic Wormhole\n"
            "Once connected, we launch "
        )
        txt.append(Text("tty-share", style="bold"))
        self.progress = Progress(
            SpinnerColumn(spinner_name="circleHalves", finished_text="✅", speed=1),
            "{task.description}",
            ##BarColumn(),
            refresh_per_second=4.0,
        )
        pane = Panel(txt, title="ShWiM", title_align="left", width=50)
        console = Console()

        from rich.table import Table
        t = self.layout = Table(show_header=False, show_lines=False, show_edge=True, padding=(0,1,1,1))
        t.add_column(justify="right", width=11)
        t.add_column(justify="left")

        self.magic_code = Text("", style="green on black", justify="center")
        self.progress

        t.add_row(Text("ShWiM", style="bold green"), txt)
        t.add_row(Text("Magic Code", style="bold red"), self.magic_code)
        t.add_row(Text("Status"), self.progress)

    def set_code(self, code):
        self.magic_code.plain = code

    def __rich__(self):
        return self.layout
