# Heishamon by Lutarym

[English](README.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · **日本語**

HeishaMon を介して Panasonic Aquarea ヒートポンプを Home Assistant に統合します。MQTT を使わず、HTTP インターフェースを直接利用します。

バージョン 1.3.1

## この統合の機能

`http://<ip>/json` を読み取り、144 個の HeishaMon トピックそれぞれにセンサーを作成します。基板が提供する場合は、高精度の電力値（XTOP）、オプション基板の値（OPT）、1-Wire 温度センサー、S0 メーターも追加します。書き込みコマンドは `http://<ip>/command?コマンド=値` を通して送られます。

すべてのトピック名、コマンド、値の範囲、エンコードは、HeishaMon ファームウェアのソースコードとドキュメント（[heishamon/HeishaMon](https://github.com/heishamon/HeishaMon) の `decode.h`、`commands.h`、`commands.cpp`、`MQTT-Topics.md`、`OptionalPCB.md`）に基づいており、推測ではありません。

## 必要条件

- Home Assistant 2024.11.0 以降
- ネットワーク上で HeishaMon 基板に接続できること

## インストール

### 手動

1. `custom_components/heishamon_lutarym` フォルダを `<config>/custom_components/` にコピーします
2. Home Assistant を再起動します
3. 設定、デバイスとサービス、統合を追加、「Heishamon by Lutarym」

### HACS

プロジェクトをカスタムリポジトリ（Custom Repository）としてカテゴリ **Integration** で追加し、インストール後に Home Assistant を再起動します。

## 設定

| 項目 | 意味 |
|---|---|
| IP アドレス | HeishaMon 基板のアドレス |
| ユーザー名、パスワード | HeishaMon で設定されている場合のみ必要 |
| 更新間隔 | 秒単位の間隔、既定 5、範囲 1〜300 |
| 読み取り専用 | オン：センサーのみ。オフ：制御も追加 |
| 表示の安定化 | 整数の温度値のばらつきを抑えます |
| 必要な連続回数 | 新しい値が確定するまでの確認回数、2〜20 |
| 外部電力計 | 任意。ヒートポンプのみを計測する電力センサー（例：Shelly） |

更新間隔、制御モード、安定化、電力計は「設定」から、アドレス、ユーザー名、パスワードは「再設定」からあとで変更できます。アドレスを変更しても、デバイス、エンティティ、履歴は保持されます。

## エンティティ

1 つのデバイスに、以下が含まれます。

| 種類 | 数 | 条件 |
|---|---|---|
| センサー TOP0〜TOP143 | 144 | 常に |
| センサー XTOP0〜XTOP5（高精度の電力値） | 6 | ヒートポンプが送信する場合（K/L シリーズ以降） |
| センサー OPT0〜OPT6 | 7 | HeishaMon でオプション基板のエミュレーションが有効な場合 |
| 1-Wire 温度センサー | センサーごとに 1 つ | HeishaMon で 1-Wire が有効な場合 |
| S0 メーター、電力と積算値 | ポートごとに 2 つ | HeishaMon で S0 が有効な場合 |
| COP 暖房、COP 給湯 | 2 | 常に |
| 選択 COP の算出元 | 1 | 外部電力計がある場合、読み取り専用でも作成 |
| 設定値（Number） | 36 | 制御が有効な場合のみ |
| スイッチ | 17 | 制御が有効な場合のみ |
| 選択リスト | 11 | 制御が有効な場合のみ |
| ボタン「エラーリセット」 | 1 | 制御が有効な場合のみ |
| オプション基板：設定値 8、スイッチ 2、選択 3 | 13 | 制御が有効で、エミュレーションが有効な場合のみ |

XTOP、OPT、1-Wire、S0 は統合の読み込み時に検出されます。あとから追加した場合は、統合を再読み込みしてください。

表示名は Home Assistant の言語設定に従います。利用できるのはドイツ語、英語、フランス語、日本語です。設定言語がこれに含まれない場合は英語が使われます。エンティティ ID には基板のアドレスと TOP 番号が含まれ、言語に依存しないため、言語を切り替えてもオートメーションは壊れません。

アドレス 192.168.1.50 のトピック TOP5 の例（`sensor.heishamon_192_168_1_50_top5`）：

| 言語 | 表示名 |
|---|---|
| ドイツ語 | TOP5 Rücklauftemperatur |
| 英語 | TOP5 Return water temperature |
| フランス語 | TOP5 Température retour d'eau |
| 日本語 | TOP5 戻り水温度 |

名前は逐語訳ではなく、分かりやすさを優先して付けています。たとえば `Ipm_Temp` は「パワーエレクトロニクス温度」、`Sterilization_State` は「レジオネラ殺菌運転中」になります。

HeishaMon が提供する説明テキストは、各エンティティの属性 `beschreibung` として利用できます。

### COP

暖房と給湯は別々に計算されます。COP は、現在の運転の熱量を電力量で割った値で、運転時間の長さに関係ありません。運転は圧縮機の起動で始まり、圧縮機が停止するか三方弁（TOP20）が運転モードを切り替えると終わります。その後は「不明」になります。除霜は電力を使い、水から熱を奪うため、運転の一部として扱われます。冷房は対象外です。

エネルギーは、問い合わせのたびに「電力 × 前回の問い合わせからの時間」として積算されます。

「COP の算出元」で、表示する値の算出元を選びます。切り替えはすぐに反映され、両方の計算は常に裏で行われています。選択は再起動後も保持されます。

| COP の算出元 | 熱量 | 電力量 |
|---|---|---|
| ヒートポンプ | ヒートポンプの報告値 | ヒートポンプの報告値 |
| 実測（電力計） | 体積流量 × 密度 × 比熱 × (往き − 戻り) | 外部電力計 |

水の密度と比熱は、平均水温における表の値から求めます。そのため、回路に不凍液（グリコール）を使用している場合、実測 COP は正しくありません。

K/L シリーズ以降の機種は正確な電力値（XTOP0〜XTOP5）を送信し、その場合はそれが使われます。それ以前の機種は 200 W 単位でしか電力を送信しないため、ヒートポンプ報告値による COP は粗い値になります。使用している値は属性 `werte`（XTOP または TOP）で確認できます。

電力計はヒートポンプのみを計測し、W、kW、mW、MW のいずれかで値を報告する必要があります。

COP がカルノー限界（往き温度と外気温度から求める理論上の最大値）を超える場合、物理的にありえないため「不明」と表示されます。

センサーの属性：`quelle`、`waermemenge_kwh`、`strommenge_kwh`、`laufzeit_min`。

## 制御

重要：HeishaMon 基板は、値を破棄した場合でも、すべてのコマンドに「OK」と応答します。そのため統合は送信前にすべての値を確認し、有効範囲外であれば画面にエラーを表示します。基板に接続できない場合もエラーが表示されます。

### 設定値

| トピック | コマンド | 範囲 |
|---|---|---|
| TOP9 | SetDHWTemp | 40〜75 °C |
| TOP27、TOP34 | SetZ1/Z2HeatRequestTemperature | ゾーンを参照 |
| TOP28、TOP35 | SetZ1/Z2CoolRequestTemperature | ゾーンを参照 |
| TOP77 | SetHeatingOffOutdoorTemp | 5〜35 °C |
| TOP78 | SetHeaterOnOutdoorTemp | -15〜20 °C |
| TOP95 | SetMaxPumpDuty | 64〜254 |
| TOP23 | SetFloorHeatDelta | 1〜15 K |
| TOP24 | SetFloorCoolDelta | 1〜15 K |
| TOP22 | SetDHWHeatDelta | -12〜-2 K |
| TOP113 | SetBufferDelta | 0〜10 K |
| TOP131 | SetBivalentStartTemp | -15〜35 °C |
| TOP134 | SetBivalentAPStartTemp | -15〜35 °C |
| TOP135 | SetBivalentAPStopTemp | -15〜35 °C |
| TOP70 | SetSterilizationTemp | 55〜75 °C |
| TOP71 | SetSterilizationMaxTime | 5〜60 分（5 分単位） |
| TOP96 | SetHeaterDelayTime（J シリーズのみ） | 0〜254 分 * |
| TOP97 | SetHeaterStartDelta（J シリーズのみ） | -127〜127 K * |
| TOP98 | SetHeaterStopDelta（J シリーズのみ） | -127〜127 K * |
| TOP29〜TOP32、TOP72〜TOP75、TOP82〜TOP89 | SetCurves（暖房・冷房曲線、ゾーン 1 と 2） | -127〜127 °C * |

\* HeishaMon のドキュメントには範囲の記載がありません。この上下限はファームウェアのエンコードによるものです。ヒートポンプがどの値を受け付けるかは分かっていません。

曲線の各点は 1 つずつ送信されます。小型の HeishaMon 基板（ESP8266）は 1 回のリクエストで 128 バイトしか処理できず、曲線全体を一度に送ることはできません。

### ゾーン

HeishaMon のドキュメントによると、有効な範囲は、ゾーンが暖房曲線で動作しているか、直接温度で動作しているかによって異なります。ヒートポンプはこれを TOP76（暖房）と TOP81（冷房）で報告します。設定値の範囲はそれに合わせて変わります。

| | 暖房曲線（シフト） | 直接温度 |
|---|---|---|
| 暖房 | -5〜5 | 20〜75 °C |
| 冷房 | -5〜5 | 5〜20 °C |

直接暖房について、ドキュメントには「20〜最大値」とあります。75 °C は HeishaMon が記載している最も高い水温設定値です。実際の最大値は機種によって異なります。

HeishaMon のドキュメントによると、サーモスタットまたはサーミスタ運転では、直接温度はこれらの値ではなく、暖房曲線の上側の点で設定します。

### 選択リスト

| コマンド | 選択肢 |
|---|---|
| SetOperationMode | 暖房、冷房、自動、給湯、暖房＋給湯、冷房＋給湯、自動＋給湯 |
| SetQuietMode | オフ、レベル 1〜3 |
| SetPowerfulMode | オフ、30、60、90 分 |
| SetZones | ゾーン 1、ゾーン 2、両方 |
| SetExternalPadHeater | オフ、タイプ A、タイプ B |
| SetBivalentMode | 代替、並列、高度並列 |
| SetHeatingControl | 快適、効率 |
| SetSmartDHW | 可変、標準 |
| SetQuietModePriority | 騒音、能力 |
| SetPumpFlowrateMode | 温度差、最大流量 |
| SetDHWSensorSelection | 上部、中央（K/L シリーズ一体型のみ） |

ヒートポンプは運転モードとして「自動（冷房）」と「自動（冷房）＋給湯」も報告します。これらはそれぞれ自動、自動＋給湯として表示されます。

### スイッチとボタン

スイッチは 17 個あり、ヒートポンプの入切、給湯強制運転、強制除霜、殺菌運転開始、非常用ヒーター、ホリデーモード、スケジュール、バッファタンク、外部制御、バイバレント制御、暖房と給湯の補助ヒーターなどが含まれます。

ボタン「エラーリセット」は、リモコンのリセットボタンと同様に、発生中のヒートポンプのエラー（例：H72）を解除します。

### オプション基板

HeishaMon でオプション基板のエミュレーションが有効な場合のみです。HeishaMon のドキュメントによると、この機能は試験的なもので、基板の送信が約 40 秒途切れると、ヒートポンプはエラー H74 で待機状態になります。先に [OptionalPCB.md](https://github.com/heishamon/HeishaMon/blob/master/OptionalPCB.md) をお読みください。

| コマンド | 種類 |
|---|---|
| SetSmartGridMode | 選択：通常、能力 1、ヒートポンプと給湯オフ、能力 2 |
| SetExternalThermostat1State、SetExternalThermostat2State | 選択：要求なし、冷房、暖房、両方 |
| SetHeatCoolMode、SetCompressorState | スイッチ |
| SetDemandControl | 値 43〜234（ドキュメントでは 5 %〜100 %） |
| SetPoolTemp、SetBufferTemp、SetZ1RoomTemp、SetZ1WaterTemp、SetZ2RoomTemp、SetZ2WaterTemp、SetSolarTemp | 温度 -78〜120 °C |

基板はこれらの値を返しません。最後に設定した値が表示され、再起動後も保持されます。`SetOptPCBByte9` は、ドキュメントに意味の記載がないため組み込んでいません。

## 既知の制限

- ゾーンは Number と Select で表現されており、Climate エンティティはありません。
- 基板の OpenTherm セクションは使用していません。
- 値の範囲は HeishaMon のドキュメントに基づいており、ヒートポンプの機種によって異なる場合があります。
- オプション基板のコマンドと SmartGrid の対応は HeishaMon のドキュメントに従っていますが、実機のヒートポンプでは試験していません。
- フランス語と日本語の翻訳は、ネイティブスピーカーによる確認を受けていません。

## ライセンス

MIT, 2026 Lutarym
