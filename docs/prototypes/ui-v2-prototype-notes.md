# 饭票二维码核销系统 UI V2 原型说明

## 设计方向

- 参考 ASXS API 后台的深色主题、左侧导航、顶部状态栏、半透明深色卡片、轻描边和高信息密度。
- 面向企业内部行政和饭堂场景，状态色控制在绿色、青色、琥珀色、红色四类，分别对应正常、信息、待处理、失败/预警。
- 桌面端以表格和筛选为核心，移动端以任务卡片和结果反馈为核心。
- 饭票二维码票面使用浅色票据风格，便于企业微信图片转发和手机展示。

## 原型画板

桌面端：

- `desktop-dashboard.png`：数据总览
- `desktop-tickets.png`：饭票记录
- `desktop-create.png`：饭票生成
- `desktop-bindings.png`：企微用户绑定
- `desktop-ops.png`：系统设置与日志概览
- `desktop-users.png`：权限管理
- `desktop-logs.png`：日志中心

移动端：

- `mobile-admin.png`：后台工作台
- `mobile-tickets.png`：饭票记录
- `mobile-create.png`：饭票生成
- `mobile-bindings.png`：企微用户绑定
- `mobile-ops.png`：系统运维
- `mobile-verify.png`：手机扫码核销结果
- `mobile-balance.png`：用户饭卡余额

票据：

- `ticket-card.png`：企业微信接收的饭票二维码图片

## 开发落地建议

- 继续使用现有 Vue + Element Plus，不需要重写技术栈。
- 建议优先落地主题变量、导航、顶部栏、表格密度、移动端分流布局。
- 饭票二维码图片可单独优化，不依赖前端框架。
- 移动核销页保持极简，只显示核销结果、失败原因和饭票关键信息。
