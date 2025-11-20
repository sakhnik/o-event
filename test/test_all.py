from o_event.models import Base, Config
from o_event.iof_importer import IOFImporter
from o_event.csv_importer import CSVImporter
from o_event.card_processor import CardProcessor, PunchReadout

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from pathlib import Path


class MockPrinter:
    def __init__(self):
        self.parts = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        ...

    def __getattr__(self, name):
        def mocked_method(*args, **kwargs):
            return None
        return mocked_method

    def text(self, t):
        self.parts.append(t)

    def get_output(self):
        return [line.rstrip() for line in ''.join(self.parts).split('\n')]


def test_all():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    Config.create(session, "O-Halloween", date(2025, 11, 15), "John Doe", "Jane Smith", "Kyiv")
    Config.set(session, Config.KEY_CURRENT_DAY, 1)

    importer = IOFImporter(session)

    data_path = Path(__file__).parent / "data" / "15.xml"
    importer.import_stage(data_path, day=1, stage_name="Спринт")
    data_path = Path(__file__).parent / "data" / "16.xml"
    importer.import_stage(data_path, day=2, stage_name="Середня")

    data_path = Path(__file__).parent / "data" / "runners.csv"
    CSVImporter.import_competitors(session, data_path)

    # 16, 149, 32, 15, 101, 82, 114, 64
    runner16 = """
        {"stationNumber":1,"cardNumber":16,"startTime":60386,"finishTime":62341,"checkTime":60386,"punches":[
            {"cardNumber":16,"code":70,"time":60419},{"cardNumber":16,"code":56,"time":60463},{"cardNumber":16,"code":75,"time":60516},
            {"cardNumber":16,"code":53,"time":60551},{"cardNumber":16,"code":74,"time":60570},{"cardNumber":16,"code":54,"time":60587},
            {"cardNumber":16,"code":73,"time":60605},{"cardNumber":16,"code":76,"time":60622},{"cardNumber":16,"code":57,"time":60665},
            {"cardNumber":16,"code":77,"time":60676},{"cardNumber":16,"code":58,"time":60738},{"cardNumber":16,"code":79,"time":60847},
            {"cardNumber":16,"code":65,"time":60876},{"cardNumber":16,"code":69,"time":60914},{"cardNumber":16,"code":55,"time":60934},
            {"cardNumber":16,"code":52,"time":60940},{"cardNumber":16,"code":63,"time":60974},{"cardNumber":16,"code":49,"time":60991},
            {"cardNumber":16,"code":61,"time":61007},{"cardNumber":16,"code":67,"time":61061},{"cardNumber":16,"code":71,"time":61104},
            {"cardNumber":16,"code":78,"time":61117},{"cardNumber":16,"code":64,"time":61181},{"cardNumber":16,"code":59,"time":61221},
            {"cardNumber":16,"code":51,"time":61241},{"cardNumber":16,"code":50,"time":61259},{"cardNumber":16,"code":60,"time":61278},
            {"cardNumber":16,"code":42,"time":61401},{"cardNumber":16,"code":47,"time":61488},{"cardNumber":16,"code":39,"time":61569},
            {"cardNumber":16,"code":34,"time":61616},{"cardNumber":16,"code":37,"time":61680},{"cardNumber":16,"code":35,"time":61735},
            {"cardNumber":16,"code":45,"time":61821},{"cardNumber":16,"code":33,"time":61946},{"cardNumber":16,"code":36,"time":61967},
            {"cardNumber":16,"code":32,"time":61989},{"cardNumber":16,"code":38,"time":62043},{"cardNumber":16,"code":48,"time":62091},
            {"cardNumber":16,"code":44,"time":62168},{"cardNumber":16,"code":43,"time":62211},{"cardNumber":16,"code":46,"time":62231},
            {"cardNumber":16,"code":31,"time":62287},{"cardNumber":16,"code":40,"time":62307},{"cardNumber":16,"code":100,"time":62337}
        ]}"""
    readout = PunchReadout.model_validate_json(runner16)
    with MockPrinter() as printer:
        assert CardProcessor().handle_card(session, readout, printer) == {"status": "OK"}
        #with open("/tmp/c.txt", "w") as f:
        #    f.write(printer.get_output())
        receipt16 = [
            '================================================',
            'E1 - O-Halloween',
            '2025-11-15 Kyiv',
            '------------------------------------------------',
            'Віктор Лисенко                     Ч21Е',
            'Ч21Е                               1.250km 0m',
            'Check: 16:46:26            Finish: 17:19:01',
            'Start: 16:46:26            SI:16',
            '================================================',
            ' 1.  70      0:33      0:33              ~34:22',
            ' 2.  56      1:17      0:44               ~8:44',
            ' 3.  75      2:10      0:53              ~29:27',
            ' 4.  53      2:45      0:35               ~6:47',
            ' 5.  74      3:04      0:19              ~14:24',
            ' 6.  54      3:21      0:17               ~5:21',
            ' 7.  73      3:39      0:18               ~8:49',
            ' 8.  76      3:56      0:17               ~9:08',
            ' 9.  57      4:39      0:43              ~11:02',
            '10.  77      4:50      0:11              ~10:47',
            '11.  58      5:52      1:02              ~17:13',
            '12.  79      7:41      1:49              ~46:35',
            '13.  65      8:10      0:29               ~4:59',
            '14.  69      8:48      0:38              ~19:48',
            '15.  55      9:08      0:20              ~20:50',
            '16.  52      9:14      0:06               ~6:15',
            '17.  63      9:48      0:34               ~8:27',
            '18.  49     10:05      0:17              ~21:48',
            '19.  61     10:21      0:16               ~7:37',
            '20.  67     11:15      0:54               ~8:34',
            '21.  71     11:58      0:43               ~9:26',
            '22.  78     12:11      0:13               ~7:44',
            '23.  64     13:15      1:04              ~10:21',
            '24.  59     13:55      0:40              ~60:36',
            '25.  51     14:15      0:20              ~12:49',
            '26.  50     14:33      0:18              ~13:03',
            '27.  60     14:52      0:19              ~35:11',
            '28.  42     16:55      2:03              ~28:05',
            '29.  47     18:22      1:27               ~8:50',
            '30.  39     19:43      1:21               ~7:48',
            '31.  34     20:30      0:47               ~9:55',
            '32.  37     21:34      1:04              ~23:11',
            '33.  35     22:29      0:55               ~8:34',
            '34.  45     23:55      1:26              ~25:36',
            '35.  33     26:00      2:05              ~13:32',
            '36.  36     26:21      0:21              ~12:30',
            '37.  32     26:43      0:22              ~21:34',
            '38.  38     27:37      0:54               ~8:44',
            '39.  48     28:25      0:48              ~11:46',
            '40.  44     29:42      1:17               ~8:33',
            '41.  43     30:25      0:43              ~11:12',
            '42.  46     30:45      0:20              ~10:45',
            '43.  31     31:41      0:56              ~13:44',
            '44.  40     32:01      0:20               ~9:48',
            '45. 100     32:31      0:30              ~13:53',
            '     OK     32:35',
            '================================================',
            'поточне відставання: —',
            'турнірна таблиця: —         26:04min/km',
            ''
        ]
        assert printer.get_output() == receipt16
