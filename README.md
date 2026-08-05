此项目为 [Home Assistant](https://www.home-assistant.io/) 的[巴法云](https://cloud.bemfa.com/)插件。

## 功能
将 Home Assistant 实体同步至巴法云，并使用小爱同学/天猫精灵/小度音箱控制。
修改了switch的触发逻辑，不判断当前状态，直接执行开关逻辑

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

## 使用
  1. 注册巴法云账号，并获取密钥
  2. 在HACS中搜索 bemfa 安装，或者 clone 此项目, 将 custom\_components/bemfa 目录拷贝至 Home Assistant 配置目录的 custom\_components 目录下。
  3. 重启 Home Assistant 服务。
  4. 在 Home Assistant 的集成页面，搜索 "bemfa" 并添加。
  5. 根据提示输入巴法云密钥后提交
  6. 安装成功后，点击集成左下角“选项”，同步需要的实体至巴法云。
  7. 在智能音箱App中添加巴法云设备:
     * 小爱同学: 在米家app-->我的-->其他平台设备-->点击添加-->找到"巴法"，输入巴法云账号即可，设备会自动同步到米家。
     * 天猫精灵: 打开天猫精灵app，在app中搜索：巴法云。找到巴法云技能，点击绑定账号，登陆你的巴法云账号.
     * 小度音箱: 打开小度音箱app或者小度app，在app首页点+号-->添加设备-->搜索巴法，找到"巴法"，输入巴法云账号即可。

## 支持的实体类型

巴法云设备类型有限，本插件将其映射为以下几种设备：

| 巴法云设备类型 | 同步的 Home Assistant 实体 |
| --- | --- |
| 开关 | `switch`、`script`、`input_boolean`、`automation`、`humidifier`、`remote`、`siren`、`camera`、`media_player`、`lock`、`scene`、`group`、`vacuum`、`button` |
| 灯 | `light` |
| 风扇 | `fan` |
| 窗帘 | `cover` |
| 空调 | `climate` |
| 传感器 | `sensor`（按区域聚合）、`binary_sensor`、`number`、`device_tracker` |

说明：

  - 巴法云不支持的部分实体（如扫地机/脚本/自动化/场景/分组/摄像机/加湿器/媒体播放器/锁/遥控器/汽笛/按钮）会被虚拟成开关类设备，可通过语音开关。
  - 传感器为只读设备：`sensor` 按区域聚合，可将区域内的温度/湿度/光照/pm2.5/co2 传感器组合为一个巴法云传感器；`binary_sensor`、`number`、`device_tracker` 则同步其当前状态/数值，只能语音查询，不能控制。
  - `button` 无持续状态，巴法云中始终显示为关闭，每次语音"打开"触发一次按压。
  - 对每种语音助手的支持各有稍许区别，例如小度音箱不支持风扇的摇头控制，具体参考[巴法云文档](https://cloud.bemfa.com/docs/#/)。

## 优势
  1. 操作简单，只需要下载一个插件，且是可视化配置。
  2. 无需公网 ip, 无需 NR.

## 原理
巴法云使用 MQTT 与终端设备通信，每个设备对应一个主题。

此插件根据用户选择的需要同步的实体，调用巴法云 API 创建对应主题，将此实体的实时状态发布至此主题，并订阅此主题的信息以控制它。

## Q/A
  - Q: 为什么调节灯的颜色时却是调的色温？

    A: 巴法云中灯的颜色和色温为同一个字段，此插件中无法精确区分。如果你的灯既可以调节颜色又可以调节色温，可能会出现混乱的情况。

  - Q: Home Assistant 中米家的设备本就支持小爱同学配置，还需同步至巴法云么？

    A: 不需要，并且不建议同步, 没必要经过巴法云绕一圈。

  - Q: 同时有小爱同学和天猫精灵，如何只同步非米家设备至小爱同学，并同步所有设备至天猫精灵？

    A: 目前没有太好的方案，一个可行的方案是注册2个巴法云账号，分别配置不同的插件实体进行同步，然后将2个账号分别绑定到小爱同学和天猫精灵。
