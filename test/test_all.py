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
        receipt16 = [
            '================================================',
            'E1 - O-Halloween',
            '2025-11-15 Kyiv',
            '------------------------------------------------',
            'Віктор Лисенко                              Ч21Е',
            'Ч21Е                                   1.25km 0m',
            'Check: 16:46:26                 Finish: 17:19:01',
            'Start: 16:46:26                            SI:16',
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
            '     OK     32:35      0:04',
            '================================================',
            'поточне відставання: +0:00',
            'турнірна таблиця: 1/1                26:04min/km',
            ''
        ]
        assert printer.get_output() == receipt16

    # 149, 32, 15, 101, 82, 114, 64

    runner149 = """
        {"stationNumber":1,"cardNumber":149,"startTime":59737,"finishTime":61836,"checkTime":59737,"punches":[
            {"cardNumber":149,"code":70,"time":59755},{"cardNumber":149,"code":56,"time":59793},{"cardNumber":149,"code":75,"time":59846},
            {"cardNumber":149,"code":53,"time":59897},{"cardNumber":149,"code":54,"time":59950},{"cardNumber":149,"code":73,"time":59967},
            {"cardNumber":149,"code":76,"time":59989},{"cardNumber":149,"code":57,"time":60020},{"cardNumber":149,"code":77,"time":60042},
            {"cardNumber":149,"code":58,"time":60097},{"cardNumber":149,"code":71,"time":60134},{"cardNumber":149,"code":79,"time":60152},
            {"cardNumber":149,"code":65,"time":60177},{"cardNumber":149,"code":69,"time":60215},{"cardNumber":149,"code":55,"time":60233},
            {"cardNumber":149,"code":52,"time":60239},{"cardNumber":149,"code":49,"time":60276},{"cardNumber":149,"code":63,"time":60315},
            {"cardNumber":149,"code":49,"time":60327},{"cardNumber":149,"code":61,"time":60342},{"cardNumber":149,"code":67,"time":60415},
            {"cardNumber":149,"code":71,"time":60454},{"cardNumber":149,"code":78,"time":60466},{"cardNumber":149,"code":64,"time":60537},
            {"cardNumber":149,"code":59,"time":60554},{"cardNumber":149,"code":51,"time":60573},{"cardNumber":149,"code":50,"time":60589},
            {"cardNumber":149,"code":60,"time":60653},{"cardNumber":149,"code":42,"time":60747},{"cardNumber":149,"code":47,"time":60845},
            {"cardNumber":149,"code":39,"time":60947},{"cardNumber":149,"code":34,"time":61002},{"cardNumber":149,"code":37,"time":61081},
            {"cardNumber":149,"code":35,"time":61148},{"cardNumber":149,"code":45,"time":61251},{"cardNumber":149,"code":33,"time":61400},
            {"cardNumber":149,"code":36,"time":61419},{"cardNumber":149,"code":32,"time":61447},{"cardNumber":149,"code":38,"time":61510},
            {"cardNumber":149,"code":48,"time":61564},{"cardNumber":149,"code":44,"time":61654},{"cardNumber":149,"code":43,"time":61692},
            {"cardNumber":149,"code":46,"time":61720},{"cardNumber":149,"code":31,"time":61782},{"cardNumber":149,"code":40,"time":61803},
            {"cardNumber":149,"code":100,"time":61834}
        ]}"""
    readout = PunchReadout.model_validate_json(runner149)
    with MockPrinter() as printer:
        assert CardProcessor().handle_card(session, readout, printer) == {"status": "MP"}
        #with open("/tmp/c.txt", "w") as f:
        #    f.write(printer.get_output())
        receipt149 = [
            '================================================',
            'E1 - O-Halloween',
            '2025-11-15 Kyiv',
            '------------------------------------------------',
            'Юрій Поліщук                                Ч21Е',
            'Ч21Е                                   1.25km 0m',
            'Check: 16:35:37                 Finish: 17:10:36',
            'Start: 16:35:37                           SI:149',
            '================================================',
            ' 1.  70      0:18      0:18              ~18:45',
            ' 2.  56      0:56      0:38               ~7:32',
            ' 3.  75      1:49      0:53              ~29:27',
            ' 4.  53      2:40      0:51     +0:16     ~9:53',
            ' 5.  74     -----     -----',
            ' 6.  54      3:33     -----',
            ' 7.  73      3:50      0:17               ~8:20',
            ' 8.  76      4:12      0:22     +0:05    ~11:50',
            ' 9.  57      4:43      0:31               ~7:57',
            '10.  77      5:05      0:22     +0:11    ~21:34',
            '11.  58      6:00      0:55              ~15:17',
            '12.  79      6:55      0:55              ~23:30',
            '13.  65      7:20      0:25               ~4:18',
            '14.  69      7:58      0:38              ~19:48',
            '15.  55      8:16      0:18              ~18:45',
            '16.  52      8:22      0:06               ~6:15',
            '17.  63      9:38      1:16     +0:42    ~18:54',
            '18.  49      9:50      0:12              ~15:23',
            '19.  61     10:05      0:15               ~7:09',
            '20.  67     11:18      1:13     +0:19    ~11:35',
            '21.  71     11:57      0:39               ~8:33',
            '22.  78     12:09      0:12               ~7:09',
            '23.  64     13:20      1:11     +0:07    ~11:29',
            '24.  59     13:37      0:17              ~25:45',
            '25.  51     13:56      0:19              ~12:11',
            '26.  50     14:12      0:16              ~11:36',
            '27.  60     15:16      1:04     +0:45   ~118:31',
            '28.  42     16:50      1:34              ~21:28',
            '29.  47     18:28      1:38     +0:11     ~9:58',
            '30.  39     20:10      1:42     +0:21     ~9:50',
            '31.  34     21:05      0:55     +0:08    ~11:36',
            '32.  37     22:24      1:19     +0:15    ~28:37',
            '33.  35     23:31      1:07     +0:12    ~10:26',
            '34.  45     25:14      1:43     +0:17    ~30:39',
            '35.  33     27:43      2:29     +0:24    ~16:08',
            '36.  36     28:02      0:19              ~11:19',
            '37.  32     28:30      0:28     +0:06    ~27:27',
            '38.  38     29:33      1:03     +0:09    ~10:12',
            '39.  48     30:27      0:54     +0:06    ~13:14',
            '40.  44     31:57      1:30     +0:13    ~10:00',
            '41.  43     32:35      0:38               ~9:54',
            '42.  46     33:03      0:28     +0:08    ~15:03',
            '43.  31     34:05      1:02     +0:06    ~15:12',
            '44.  40     34:26      0:21     +0:01    ~10:18',
            '45. 100     34:57      0:31     +0:01    ~14:21',
            '   DISQ     34:59      0:02',
            '================================================',
            'поточне відставання: +0:00',
            '                                     27:59min/km',
            ''
        ]
        assert printer.get_output() == receipt149
