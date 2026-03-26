"""数据项定义 — 不可变数据类"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class DataItem:
    id: str
    name: str
    description: str
    safety_level: str          # "safe" | "caution" | "forbidden"
    paths: tuple[str, ...]     # 相对于 T0002 的路径，文件或目录
    is_directory: bool = False  # 路径列表中是否含目录


ALL_DATA_ITEMS: tuple[DataItem, ...] = (
    DataItem(
        id="blocknew",
        name="自定版块和自选股",
        description=(
            "包含用户自定义的板块分类和自选股列表，以及版块配置文件。"
            "这是最重要的个人数据，丢失后需要重新手动添加所有自选股和自建板块。"
        ),
        safety_level="safe",
        paths=("blocknew", "blocknew.cfg"),
        is_directory=True,
    ),
    DataItem(
        id="indicators",
        name="指标及指标模板",
        description=(
            "用户编写的技术分析公式指标和指标模板。"
            "PriBand=波段指标, PriCS=参数精灵, PriGS=公式, "
            "PriLoc=本地指标, PriPack/PriPack_def=指标包。"
            "新版本可能只有4个文件，旧版本最多7个。"
        ),
        safety_level="safe",
        paths=(
            "PriBand.dat",
            "PriCS.dat",
            "PriDefault.dat",
            "PriGS.dat",
            "PriLoc.dat",
            "PriPack.dat",
            "PriPack def.dat",   # 旧版本（含空格）
            "PriPack_def.dat",   # 新版本（下划线）
        ),
    ),
    DataItem(
        id="indicator_dll",
        name="指标DLL",
        description=(
            "部分自编公式依赖的外部DLL动态链接库文件。"
            "如果公式中调用了DLL函数，必须同时迁移此文件夹，否则相关指标将无法运行。"
            "新版本目录名为 dlls/，旧版本为 dll/。"
        ),
        safety_level="safe",
        paths=("dll", "dlls"),
        is_directory=True,
    ),
    DataItem(
        id="signals",
        name="自定义数据",
        description=(
            "用户自定义的信号数据，包括条件选股结果、预警触发记录等自定义数据文件。"
        ),
        safety_level="safe",
        paths=("signals",),
        is_directory=True,
    ),
    DataItem(
        id="scheme",
        name="配色方案",
        description=(
            "通达信界面的颜色配置方案，包括K线颜色、背景色、均线颜色等所有视觉设置。"
            "迁移后可保持一致的视觉体验。文件名可能为 Scheme.dat 或 scheme.dat。"
        ),
        safety_level="safe",
        paths=("Scheme.dat", "scheme.dat"),
    ),
    DataItem(
        id="tpool",
        name="策略股池",
        description=(
            "策略股票池数据，包含用户设置的策略筛选条件和对应的股票池结果。"
        ),
        safety_level="safe",
        paths=("tpoo",),
        is_directory=True,
    ),
    DataItem(
        id="note",
        name="金融记事本",
        description="金融记事本中保存的笔记数据，包括个股笔记、交易日记等用户录入的文字记录。",
        safety_level="safe",
        paths=("note",),
        is_directory=True,
    ),
    DataItem(
        id="cmd_tools",
        name="配置工具脚本（cmd）",
        description="开心果整合版 T0002\\cmd 目录下的配置工具脚本、配置与说明文件。用于辅助板块/配置相关操作。",
        safety_level="safe",
        paths=("cmd", "修复板块.bat"),
        is_directory=True,
    ),
    DataItem(
        id="screening_profiles",
        name="条件选股/策略文件（*.czs/*.cos）",
        description="通达信 T0002 根目录下保存的条件选股/策略文件（如 *.czs、*.cos），通常为用户自定义/收藏筛选条件。",
        safety_level="safe",
        paths=("*.czs", "*.cos"),
    ),
    DataItem(
        id="pad",
        name="版面配置（本地）",
        description=(
            "用户自定义的本地界面版面布局，包括分析页面、多窗口排列等个性化界面配置。"
            "不同版本间版面格式可能不兼容，谨慎应用。"
        ),
        safety_level="caution",
        paths=("pad",),
        is_directory=True,
    ),
    DataItem(
        id="cloud_pad",
        name="版面配置（云端缓存）",
        description=(
            "云端版面的本地缓存目录（cloud_pad 至 cloud_pad7）。"
            "包含从云端下载并本地应用的版面方案，迁移后可恢复自定义云版面布局。"
        ),
        safety_level="caution",
        paths=(
            "cloud_pad",
            "cloud_pad2",
            "cloud_pad3",
            "cloud_pad4",
            "cloud_pad5",
            "cloud_pad6",
            "cloud_pad7",
        ),
        is_directory=True,
    ),
    DataItem(
        id="colwidth",
        name="行情界面定制栏目",
        description=(
            "行情列表的栏目宽度、显示顺序和自定义列设置。"
            "不同版本的栏目结构可能变化，导入后可能引起显示异常。"
            "文件名可能为 col_width.dat 或 colwidth.dat。"
        ),
        safety_level="caution",
        paths=("col_width.dat", "colwidth.dat"),
    ),
    DataItem(
        id="wt_data",
        name="交易账户数据",
        description=(
            "委托交易相关的账户数据（支持多账号）。"
            "包含交易历史和账户配置，涉及资金安全，请确认来源可信后再导入。"
            "目录名可能为 wt_data/ 或 wt data/（含空格）。"
        ),
        safety_level="caution",
        paths=("wt_data", "wt data"),
        is_directory=True,
    ),
    DataItem(
        id="ic_data",
        name="BS落地数据",
        description=(
            "买卖点（Buy/Sell）信号的本地持久化数据。"
            "记录了指标产生的交易信号历史，用于回顾和分析。"
            "目录名可能为 lc_data/ 或 Ic data/（含空格）。"
        ),
        safety_level="caution",
        paths=("lc_data", "Ic data"),
        is_directory=True,
    ),
    DataItem(
        id="tdxline",
        name="画线数据",
        description=(
            "K线图上手动绘制的趋势线、支撑压力线、通道线等画线标注数据。"
            "通常影响不大，但偶尔会导致个别图表显示异常。"
        ),
        safety_level="caution",
        paths=("tdxline.dat",),
    ),
    DataItem(
        id="clmclnfo",
        name="预埋单策略",
        description=(
            "预埋单（条件委托）的策略配置数据。"
            "包括触发条件、委托价格、数量等参数，导入后请仔细核对条件是否正确。"
        ),
        safety_level="caution",
        paths=("clmclnfo.dat",),
    ),
    DataItem(
        id="fastxginfo",
        name="自动选股设置",
        description=(
            "快速选股/自动选股功能的筛选条件配置。"
            "包括选股公式、参数设置、筛选范围等。"
        ),
        safety_level="caution",
        paths=("fastxginfo.dat",),
    ),
    DataItem(
        id="mark",
        name="个股标记信息",
        description=(
            "个股上的标记/标签信息，如用户对特定股票设置的颜色标记、文字备注等。"
            "文件名可能为 mark.dat 或 Mark.DAT。"
        ),
        safety_level="caution",
        paths=("mark.dat", "Mark.DAT"),
    ),
    DataItem(
        id="warn",
        name="自定预警信息",
        description=(
            "自定义预警条件设置。"
            "col_tlwarn=条件预警, col_tjwarn=弹窗预警, "
            "col_tjexwarn=扩展预警, col_cfgwarn=预警配置。"
            "包含价格预警、涨跌幅预警等用户设定的监控条件。"
        ),
        safety_level="caution",
        paths=(
            "col_tlwarn.dat",
            "col_tjwarn.dat",
            "col_tjexwarn.dat",
            "col_cfgwarn.dat",
            "col cfgwarn.dat",   # 旧版本（含空格）
        ),
    ),
    DataItem(
        id="trade_helpers",
        name="交易/登录辅助文件",
        description="委托/登录相关的辅助配置（hostip.ini、clid_*.dat、jyverify.dat、usercomm.ini、syscomm.ini、wt_cache）。不同版本/券商环境可能不兼容。",
        safety_level="caution",
        paths=(
            "hostip.ini",
            "usercomm.ini",
            "syscomm.ini",
            "clid_*.dat",
            "jyverify.dat",
            "wt_cache",
            "Certi",
        ),
        is_directory=True,
    ),
    DataItem(
        id="ui_misc_settings",
        name="界面/栏目杂项配置（非 user.ini）",
        description="界面与栏目相关的杂项配置/缓存文件（不含 user.ini）。不同版本间可能存在差异，导入后如异常可取消该项或回滚。",
        safety_level="caution",
        paths=(
            "gridtab.dat",
            "recentbreed.dat",
            "stdqs.cfg",
            "user_fx.dat",
            "diycol.dat",
            "overlap.dat",
            "dtjdInfo.dat",
            "msgboxflag.dat",
            "msgtznz.dat",
            "cbset.dat",
            "clcache.dat",
            "otcache.dat",
            "CloudSvcCache.json",
            "evalexp",
            "msg_hq",
            "msg_jy",
            "msg_tq",
            "msg_zx",
        ),
        is_directory=True,
    ),
    DataItem(
        id="user_ini_forbidden",
        name="个性化配置（user.ini，禁止直接复制）",
        description="user.ini 是个性化配置核心文件，跨版本整体复制可能导致闪退；请使用“user.ini 定向同步”，普通 section 仅替换同名键，extern_* 额外追加缺失键，且不会新增段落。",
        safety_level="forbidden",
        paths=("user.ini",),
    ),
)

# 按安全级别分组
SAFE_ITEMS = tuple(i for i in ALL_DATA_ITEMS if i.safety_level == "safe")
CAUTION_ITEMS = tuple(i for i in ALL_DATA_ITEMS if i.safety_level == "caution")
FORBIDDEN_ITEMS = tuple(i for i in ALL_DATA_ITEMS if i.safety_level == "forbidden")

# 按 ID 快速查找
ITEMS_BY_ID: dict[str, DataItem] = {item.id: item for item in ALL_DATA_ITEMS}
