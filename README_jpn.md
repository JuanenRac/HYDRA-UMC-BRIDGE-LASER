<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - レーザーセル協調ブリッジ
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 [Français](README_fra.md) | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 **日本語**

レーザーセルと HYDRA-UMC ロボット補助機構のための上位ブリッジです。材料の
受け渡しなど安全な周辺タスクを協調できますが、レーザーコントローラーを
アーム、発射、またはオーバーライドすることはできません。

## アーキテクチャ

```text
レーザーコントローラー <-> BRIDGE-LASER <-> SDK <-> SERVER <-> 独立安全系
```

コントローラーがアイドルであり、キーが有効であり、エンクロージャーが閉じ、
コントローラーが健全なインターロックを報告しない限り、ブリッジはフェイル
クローズします。これらの条件は観測に過ぎず、認証済みレーザー安全の代替では
決してありません。

## ビルドとテスト

Windows では `build-test.bat`、Linux では `bash build-test.sh` を実行します。
バージョンは変更せず、安全アイドル許可、エンクロージャー拒否、中止転送を
テストします。実際のレーザーソフトウェア/コントローラーの選択は、機械と
文書化されたインターフェースが利用可能になるまで意図的に延期されます。

## 関連プロジェクト

| プロジェクト | 役割 |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | 共有安全コントラクト。 |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | 認可されたセル境界。 |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | 将来のゾーン証跡。 |

## 状態

バージョン `0.0.1` はローカルでテストされたフェイルセーフ計画コアです。
レーザーシステムへの接続や操作にはまだ使われていません。

## ⚙️ バージョン付きビルド

`build-test.bat` / `build-test.sh` はリポジトリを変更せず検証します。
`build.bat` / `build.sh` は最初にその検証を実行し、成功した場合のみネイティブ
パッケージ版、マニフェスト、`CHANGELOG.md` を同期します。安全なレーザー制御
統合の検証前にレーザー `run` コマンドはありません。
