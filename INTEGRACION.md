# Integrar «Análisis rápido» en IST-20

Paquete autónomo (solo biblioteca estándar, sin dependencias nuevas). Probado con 13 tests offline.
Los tests de red usan respuestas simuladas; **no se ha probado contra CoinGecko real ni el panel Tkinter** (sin red ni Tkinter en el entorno de desarrollo).

## 1. Copiar
Copia la carpeta `ist20_analysis/` junto a tu `app.py` (misma carpeta que `config.py` y `run.py`).
Opcional: `tests/` para ejecutar `python -m unittest tests.test_analysis`.

## 2. Panel en la aplicación (`app.py`)
```python
from ist20_analysis.provider import CoinGeckoProvider
from ist20_analysis.quick_panel import QuickAnalysisPanel

panel = QuickAnalysisPanel(contenedor, CoinGeckoProvider())
panel.pack(fill="both", expand=True)          # o notebook.add(panel, text="Análisis rápido")
```
`contenedor` es la ventana, el frame o el `ttk.Notebook` donde quieras la pestaña.

## 3. Informe por línea de comandos (`run.py`)
```python
from ist20_analysis.cli import main as analysis_main
# p. ej. si el primer argumento es "analisis":
#   if len(sys.argv) > 1 and sys.argv[1] == "analisis": sys.exit(analysis_main(sys.argv[2:]))
```
Uso directo, sin tocar `run.py`: `python -m ist20_analysis list` y `python -m ist20_analysis run sentiment`
(`run asset --coin solana`, `run mtf --coin ethereum`).

## 4. Si ya tienes tu propio cliente de CoinGecko
Los análisis solo necesitan este contrato; impleméntalo con tu código y pásalo en lugar de `CoinGeckoProvider`:
- `universe()` → lista de `Coin(id, symbol, volume)`
- `closes(coin_id, tf)` → lista de cierres, `tf` en `15m | 4h | 1d | 1w | 1M`

## Ajustes (`ist20_analysis/config.py`)
Dentro de IST-20, universo, TAO, stablecoins, derivados y URL se leen de tu `config.py` (una sola fuente de verdad). Aquí quedan sectores, filtro de volumen mínimo, caché y ritmo de peticiones.
La clave de CoinGecko (opcional) va en la variable de entorno `COINGECKO_DEMO_API_KEY`, nunca en el código.

## Límites conocidos
- Plan gratuito: ≤365 días de histórico. Mensual usa EMA 3/6 (≈12 velas); semanal ≈52 velas.
- 15 min se remuestrea desde datos de 5 min (`days=1`); no probado contra la API real.
- Un análisis de todo el universo hace ~20 peticiones; la primera vez tarda ~1 min (ritmo de 2,5 s), después sale de la caché.
- Sin volumen ni detección de patrones; acumulación/distribución y «¿buen momento?» no se calculan.
- **No incluido:** las velas de 15 min / 4 h como opción del gráfico de tu app y TAO en tu lista propia; necesito `src/` para eso.
