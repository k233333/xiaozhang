# 视频按日期分类

## triggers
- 把视频按日期分类到不同文件夹
- 按日期整理视频文件
- 大于 500MB 的视频分类管理
- 整理 D 盘视频到日期文件夹

## description
将指定磁盘（D 盘）中所有大于 500MB 的视频文件，按修改日期归类到对应的日期文件夹中。

## confirm_required
true

## steps
```json
[
  {"tier": "D", "action": "search_files", "drive": "D:", "pattern": "*.mp4,*.avi,*.mov,*.mkv,*.wmv", "min_size_mb": 500},
  {"tier": "D", "action": "get_file_properties", "property": "date_modified"},
  {"tier": "C", "action": "confirm", "message": "找到 X 个符合条件的视频文件，即将按日期归类到 YYYY-MM-DD 文件夹，是否继续？"},
  {"tier": "D", "action": "create_folders", "base_path": "D:\\Videos\\ByDate", "structure": "date_based"},
  {"tier": "C", "action": "move_files", "destination": "D:\\Videos\\ByDate\\{date_modified}\\", "option": "move"}
]
```

## learned
- 视频文件扩展名需覆盖常见格式：.mp4, .avi, .mov, .mkv, .wmv
- min_size_mb 参数单位是 MB，不要用字节
- 按修改日期归类比较通用，创建时间用户通常不关心
