-- 删除旧的飞书文件同步表（约 7GB，在 Neon 上可能需数分钟）
DROP TABLE IF EXISTS feishu_file_rows CASCADE;
DROP TABLE IF EXISTS feishu_files CASCADE;
