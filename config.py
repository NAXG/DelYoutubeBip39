# YouTube 助记词骗局检测工具配置文件

# YouTube API 配置
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
CLIENT_SECRETS_FILE = "client_secret.json"  # 从Google Cloud Console下载的OAuth 2.0客户端ID
TOKEN_FILE = "token.pickle"  # 存储用户访问令牌的文件

# 频道配置
CHANNEL_ID = "UCXXXXXXXX"  # 请替换为您的YouTube频道ID

# 助记词检测配置
# BIP39助记词通常包含12、15、18、21或24个单词
MIN_SEED_WORDS = 12  # 最少单词数量，检测到至少这么多助记词单词才会被标记

# BIP39单词列表文件路径
BIP39_WORDLIST_FILE = "english.txt"  # 包含所有BIP39助记词的文件

# 评论扫描配置
MAX_RESULTS_PER_PAGE = 100  # 每页获取的最大评论数
MAX_PAGES_PER_VIDEO = 10    # 每个视频扫描的最大页数 (减少此值可节省API配额)
DAYS_TO_SCAN = None         # 扫描所有视频，不限时间范围，可以设置 30数字表示扫描最近30天的视频

# 时间戳配置（避免重复检测）
TIMESTAMP_FILE = "last_scan_time.json"  # 存储上次扫描时间的文件
FORCE_FULL_SCAN = False  # 设置为True将忽略上次扫描时间，强制进行完整扫描

# 日志配置
LOG_FILE = "scam_detector.log"
ENABLE_CONSOLE_OUTPUT = True
