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
        txt.append(Text("tty-share\n", style="bold"))
        self.progress = Progress(
            SpinnerColumn(spinner_name="circleHalves", finished_text="✅", speed=1),
            "{task.description}",
            ##BarColumn(),
            refresh_per_second=4.0,
        )
        pane = Panel(txt, title="ShWiM", title_align="left", width=50)
        console = Console()
        # okay we're like not "absolute position" this yet
        self.layout = Layout()
        self.magic_code = Text("")
        self.layout.split_column(
            Layout(
                Align.center(Padding(pane, 2)),
            ),
            Layout(
                Align.center(
                    Panel(Align.center(Padding(self.magic_code, 1)), title="Magic Code", title_align="left", width=50),
                ),
            ),
            Layout(
                Align.center(
                    Panel(self.progress, title="Connecting", title_align="left", height=5),
                ),
            ),
        )

    def set_code(self, code):
        #self.magic_code.append(code, style="bold")
        self.magic_code.plain = code#append(code, style="bold")

    def __rich__(self):
        return self.layout
