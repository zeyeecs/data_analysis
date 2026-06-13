-- 统一 F / R / V 的 color 存储格式（在数据库端执行，避免远程逐行 UPDATE）
-- 颜色 → Title Case 英文；多色用 / 连接
-- 成色（condition）保持飞书原始值，不做档位映射

-- 1) 清理 F 表 Python 列表字面量（单元素）
UPDATE "F"
SET color = (regexp_match(color, '^\[''([^'']+)''\]$'))[1]
WHERE color ~ '^\[''[^'']+''\]$';

UPDATE "F" SET color = NULL WHERE color = '[]';

-- 2) 统一 color：别名映射（三表共用 CASE）
UPDATE "F" SET color = CASE lower(color)
    WHEN 'beige' THEN 'Beige' WHEN 'black' THEN 'Black' WHEN 'blue' THEN 'Blue'
    WHEN 'blues' THEN 'Blue' WHEN 'brown' THEN 'Brown' WHEN 'browns' THEN 'Brown'
    WHEN 'gold' THEN 'Gold' WHEN 'gray' THEN 'Gray' WHEN 'grays' THEN 'Gray'
    WHEN 'grey' THEN 'Gray' WHEN 'greys' THEN 'Gray' WHEN 'green' THEN 'Green'
    WHEN 'greens' THEN 'Green' WHEN 'khaki' THEN 'Khaki' WHEN 'metallic' THEN 'Metallic'
    WHEN 'multicolor' THEN 'Multicolor' WHEN 'multicolour' THEN 'Multicolor'
    WHEN 'neutral' THEN 'Neutral' WHEN 'orange' THEN 'Orange' WHEN 'pink' THEN 'Pink'
    WHEN 'print' THEN 'Print' WHEN 'purple' THEN 'Purple' WHEN 'purples' THEN 'Purple'
    WHEN 'red' THEN 'Red' WHEN 'reds' THEN 'Red' WHEN 'silver' THEN 'Silver'
    WHEN 'white' THEN 'White' WHEN 'whites' THEN 'White' WHEN 'yellow' THEN 'Yellow'
    WHEN 'yellows' THEN 'Yellow' WHEN 'color' THEN NULL
    ELSE initcap(color)
END
WHERE color IS NOT NULL AND color <> '' AND color NOT LIKE '[%';

UPDATE "R" SET color = CASE lower(color)
    WHEN 'beige' THEN 'Beige' WHEN 'black' THEN 'Black' WHEN 'blue' THEN 'Blue'
    WHEN 'blues' THEN 'Blue' WHEN 'brown' THEN 'Brown' WHEN 'browns' THEN 'Brown'
    WHEN 'gold' THEN 'Gold' WHEN 'gray' THEN 'Gray' WHEN 'grays' THEN 'Gray'
    WHEN 'grey' THEN 'Gray' WHEN 'greys' THEN 'Gray' WHEN 'green' THEN 'Green'
    WHEN 'greens' THEN 'Green' WHEN 'khaki' THEN 'Khaki' WHEN 'metallic' THEN 'Metallic'
    WHEN 'multicolor' THEN 'Multicolor' WHEN 'multicolour' THEN 'Multicolor'
    WHEN 'neutral' THEN 'Neutral' WHEN 'orange' THEN 'Orange' WHEN 'pink' THEN 'Pink'
    WHEN 'print' THEN 'Print' WHEN 'purple' THEN 'Purple' WHEN 'purples' THEN 'Purple'
    WHEN 'red' THEN 'Red' WHEN 'reds' THEN 'Red' WHEN 'silver' THEN 'Silver'
    WHEN 'white' THEN 'White' WHEN 'whites' THEN 'White' WHEN 'yellow' THEN 'Yellow'
    WHEN 'yellows' THEN 'Yellow' WHEN 'color' THEN NULL
    ELSE initcap(color)
END
WHERE color IS NOT NULL AND color <> '';

UPDATE "V" SET color = CASE lower(color)
    WHEN 'beige' THEN 'Beige' WHEN 'black' THEN 'Black' WHEN 'blue' THEN 'Blue'
    WHEN 'blues' THEN 'Blue' WHEN 'brown' THEN 'Brown' WHEN 'browns' THEN 'Brown'
    WHEN 'gold' THEN 'Gold' WHEN 'gray' THEN 'Gray' WHEN 'grays' THEN 'Gray'
    WHEN 'grey' THEN 'Gray' WHEN 'greys' THEN 'Gray' WHEN 'green' THEN 'Green'
    WHEN 'greens' THEN 'Green' WHEN 'khaki' THEN 'Khaki' WHEN 'metallic' THEN 'Metallic'
    WHEN 'multicolor' THEN 'Multicolor' WHEN 'multicolour' THEN 'Multicolor'
    WHEN 'neutral' THEN 'Neutral' WHEN 'orange' THEN 'Orange' WHEN 'pink' THEN 'Pink'
    WHEN 'print' THEN 'Print' WHEN 'purple' THEN 'Purple' WHEN 'purples' THEN 'Purple'
    WHEN 'red' THEN 'Red' WHEN 'reds' THEN 'Red' WHEN 'silver' THEN 'Silver'
    WHEN 'white' THEN 'White' WHEN 'whites' THEN 'White' WHEN 'yellow' THEN 'Yellow'
    WHEN 'yellows' THEN 'Yellow' WHEN 'color' THEN NULL
    ELSE initcap(color)
END
WHERE color IS NOT NULL AND color <> '';
