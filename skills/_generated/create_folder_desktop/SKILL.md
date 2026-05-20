```markdown
# 桌面新建文件夹

## triggers
- 新建文件夹
- 创建文件夹 测试文件夹
- 在桌面加个文件夹
- 新建一个文件夹叫

## description
在 Windows 桌面上创建一个指定名称的文件夹。

## confirm_required
false

## steps
```json
[
  {"tier": "D", "action": "run_cmd", "cmd": ["cmd", "/c", "cd /d C:\\Users\\k9211\\Desktop && mkdir \"{folder_name}\""], "requires_confirmation": false},
  {"tier": "D", "action": "say", "text": "文件夹已创建，就在桌面上。", "requires_confirmation": false}
]
```

## learned
- 使用 cmd /c 加 mkdir 直接创建，比 powershell 更轻量
- 文件夹名用双引号包起来避免空格或中文路径出问题
```
