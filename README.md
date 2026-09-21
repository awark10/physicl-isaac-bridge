# Nfinite Isaac Bridge

Односторонній міст 3ds Max → NVIDIA Isaac Sim для збірки сцен через USD.
Немає спільної теки чи таймера — вся домовленість зашита в структуру сцени й імена об'єктів:
кожна категорія (`STRUCTURE`, `ASSET`, `CAMERA`, світло) експортується в окремий `.usd` за
узгодженою назвою, а розширення в Isaac Sim саме розпізнає ці файли й імена маркерів, щоб
зібрати сцену назад.

Технічний огляд проєкту: **[awark10.github.io/nfinite-isaac-bridge](https://awark10.github.io/nfinite-isaac-bridge/)**
(копія лежить у [`docs/overview/`](docs/overview/))

## Структура

| Файл | Де | Роль |
|---|---|---|
| `Nfinite-IsaacTools_v1.1.ms` | 3ds Max | Основна панель експорту — Model/Structure/Asset/Camera/Light |
| `Export_To_Isaac_Sim.ms` | 3ds Max | Простіший загальний USD-експорт + автовстановлення Autodesk USD плагіна |
| `my_aligner.py` | Isaac Sim | Розширення «Scene Bridge & Aligner» — завантаження сцени за категоріями, auto-populate активів |
| `Nfnt_Model_To_Isaac_Bridge.py` | Isaac Sim | Вбудований під-інструмент — одна модель, текстури, UCX-колайдери, вимір трансформу |
| `Isaac_Sim_Align_By_Pattern.py` | Isaac Sim | Окремий скрипт вирівнювання об'єктів за числовим ID у назві (поза UI розширення) |
| `extension.toml` | Isaac Sim | Маніфест розширення «Aligner & Measure Tool» |
| `docs/overview/` | — | Технічний огляд (та сама сторінка, що й на GitHub Pages) |

## Ключова ідея

На відміну від [Substance Bridge](https://github.com/awark10/substance-bridge) (живий round-trip через
спільну теку й таймер), тут канал лише в один бік і без постійного зв'язку. Протокол — це самі
імена: VRay-світло кодується в рядок формату `_LGT_<Type>_<Intensity×1000>_<Dim0>_<Dim1>_<Name>_POS`,
маркери розміщення активів несуть ID активу прямо в імені. Розширення в Isaac Sim парсить ці імена й
відновлює справжні USD-прайми.

## Версії

- `Nfinite-IsaacTools_v1.1.ms` — v1.1.15
- `my_aligner.py` — v8.11.0
- `extension.toml` (Aligner & Measure Tool) — v2.3.0
