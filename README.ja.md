# Heishamon by Lutarym

[English](README.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · **日本語**

HeishaMon を介して Panasonic Aquarea ヒートポンプを Home Assistant に統合します。MQTT を使わず、HTTP インターフェースを直接利用します。

バージョン 1.1.0

## この統合の機能

`http://<ip>/json` を読み取り、144 個の HeishaMon トピックそれぞれに対してエンティティを作成します。書き込みコマンドは `http://<ip>/command?コマンド=値` を通して送られます。

すべてのトピック名と SET コマンドは、HeishaMon ファームウェアのソースコード（`decode.h`、`commands.h`）からそのまま取得しており、推測ではありません。

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
| 外部電力計 | 任意。ヒートポンプのみを計測する電力センサー（例：Shelly PM） |

更新間隔、制御モード、安定化、電力計は、エントリを作り直さずに「設定」からあとで変更できます。

## エンティティ

1 つのデバイスに、以下が含まれます。

- 137 個のセンサー、トピックごとに 1 つ、`sensor.heishamon_<アドレス>_top0` から `..._top143`
- 7 個の設定値（Number）、「読み取り専用」が無効の場合のみ
- 16 個のスイッチと 4 個の選択リスト、同じく制御が有効の場合のみ
- COP 暖房と COP 給湯、`sensor.heishamon_<アドレス>_cop_heating` と `..._cop_dhw`
- COP 暖房 実測と COP 給湯 実測、`..._cop_heating_measured` と `..._cop_dhw_measured`、外部電力計がある場合のみ

表示名は Home Assistant の言語設定に従います。利用できるのはドイツ語、英語、フランス語、日本語です。設定言語がこれに含まれない場合は英語が使われます。エンティティ ID には基板のアドレスと TOP 番号が含まれ、言語に依存しないため、言語を切り替えてもオートメーションは壊れません。複数の HeishaMon 基板がある場合でも、各 ID は一意のままです。

アドレス 192.168.1.50 のトピック TOP5 の例（`sensor.heishamon_192_168_1_50_top5`）：

| 言語 | 表示名 |
|---|---|
| ドイツ語 | TOP5 Ruecklauftemperatur |
| 英語 | TOP5 Return water temperature |
| フランス語 | TOP5 Temperature retour d'eau |
| 日本語 | TOP5 戻り水温度 |

名前は逐語訳ではなく、分かりやすさを優先して付けています。たとえば `Ipm_Temp` は「パワーエレクトロニクス温度」、`Sterilization_State` は「レジオネラ殺菌運転中」になります。

HeishaMon が提供する説明テキストは、各エンティティの属性 `beschreibung` として利用できます。

### COP

暖房と給湯は別々に計算されます。値が表示されるのは、圧縮機が運転中で、除霜中でなく、その運転モードが有効な場合のみです。それ以外は「不明」になります。冷房は対象外です。

| センサー | 熱出力 | 電力 |
|---|---|---|
| COP 暖房、COP 給湯 | ヒートポンプの報告値（モード別） | ヒートポンプの報告値（モード別） |
| COP 暖房 実測、COP 給湯 実測 | 流量 × 4180 × (往き − 戻り) | 外部電力計 |

実測 COP では、三方弁（TOP20）の位置によって暖房と給湯のどちらに数えるかが決まります。

K/L シリーズ以降の機種は正確な電力値（XTOP0〜XTOP5）を送信し、その場合はそれが使われます。それ以前の機種は 200 W 単位でしか電力を送信しないため、ヒートポンプ報告値による COP は粗い値になります。実測 COP の方が正確です。

電力計はヒートポンプのみを計測し、W、kW、mW、MW のいずれかで値を報告する必要があります。回路に不凍液（グリコール）を使用している場合、水の比熱で計算するため実測 COP は高めに出ます。

使用した電力値は、センサーの属性 `thermische_leistung_w` と `elektrische_leistung_w` で確認できます。

### 書き込み可能な設定値

| トピック | コマンド | 範囲 |
|---|---|---|
| TOP9 | SetDHWTemp | 40〜75 |
| TOP27 | SetZ1HeatRequestTemperature | -5〜50 |
| TOP28 | SetZ1CoolRequestTemperature | -5〜20 |
| TOP34 | SetZ2HeatRequestTemperature | -5〜50 |
| TOP35 | SetZ2CoolRequestTemperature | -5〜20 |
| TOP77 | SetHeatingOffOutdoorTemp | 5〜35 |
| TOP78 | SetHeaterOnOutdoorTemp | -15〜20 |

## 既知の制限

- ゾーンは Number と Select で表現されており、Climate エンティティはありません。
- `1wire` と `s0` セクションは読み取られますが、固定のエンティティは定義されていません。
- 設定値の範囲は HeishaMon のドキュメントに基づいており、ヒートポンプの機種によって異なる場合があります。
- フランス語と日本語の翻訳は、ネイティブスピーカーによる確認を受けていません。

## ライセンス

MIT, 2026 Lutarym
