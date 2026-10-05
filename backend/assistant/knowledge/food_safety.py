"""Datos de seguridad alimentaria (fuente: USDA FSIS "Safe Minimum Internal Temperature
Chart" y FoodSafety.gov "Cold Food Storage Chart"; valores vigentes en 2025).

El proyecto no tiene una base de datos oficial propia, así que los valores viven
aquí, con su fuente. Si cambian las recomendaciones, se actualiza este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE = "USDA FSIS / FoodSafety.gov"


@dataclass(frozen=True)
class SafetyEntry:
    id: str
    keys: tuple[str, ...]  # sin acentos
    label: str
    min_temp_c: int | None
    min_temp_f: int | None
    rest_minutes: int | None
    cooking_guidance: str
    fridge_raw: str | None = None  # conservación en crudo
    extra_warnings: tuple[str, ...] = ()


ENTRIES: tuple[SafetyEntry, ...] = (
    SafetyEntry(
        "aves_molidas", ("pollo molido", "pavo molido", "carne molida de pollo", "carne molida de pavo"),
        "aves molidas", 74, 165, None, "Cocina hasta que no quede rosado y alcance la temperatura en el centro.",
        "1-2 días en refrigeración",
    ),
    SafetyEntry(
        "aves", ("pollo", "pavo", "gallina", "pato", "pechuga", "muslo", "pierna de pollo", "alitas", "codorniz", "ave", "aves"),
        "aves (pollo, pavo, pato)", 74, 165, None,
        "Mide en la parte más gruesa sin tocar el hueso; los jugos deben salir claros, pero la temperatura es la prueba fiable.",
        "1-2 días en refrigeración",
    ),
    SafetyEntry(
        "carne_molida", ("carne molida", "molida de res", "molida de cerdo", "hamburguesa", "albondiga", "picadillo", "chorizo", "salchicha cruda"),
        "carne molida (res, cerdo, ternera, cordero)", 71, 160, None,
        "Al molerla, las bacterias de la superficie se reparten por toda la carne: cocínala completamente.",
        "1-2 días en refrigeración",
    ),
    SafetyEntry(
        "carne_entera", ("res", "cerdo", "puerco", "ternera", "cordero", "filete", "bistec", "chuleta", "lomo", "costilla", "asado", "arrachera", "solomillo", "pierna"),
        "cortes enteros de res, cerdo, ternera o cordero", 63, 145, 3,
        "Mide en la parte más gruesa y deja reposar 3 minutos antes de cortar.",
        "3-5 días en refrigeración",
    ),
    SafetyEntry(
        "jamon_crudo", ("jamon fresco", "jamon crudo sin curar"), "jamón fresco (crudo)", 63, 145, 3,
        "Igual que los cortes enteros de cerdo.", "3-5 días en refrigeración",
    ),
    SafetyEntry(
        "pescado", ("pescado", "salmon", "atun", "tilapia", "bacalao", "merluza", "robalo", "huachinango", "trucha", "mojarra", "filete de pescado"),
        "pescado", 63, 145, None,
        "La carne debe quedar opaca y separarse fácilmente con un tenedor.",
        "1-2 días en refrigeración",
        ("El pescado crudo (ceviche, sushi) no alcanza temperatura segura: usa pescado muy fresco o previamente congelado y no se recomienda para embarazadas, niños pequeños ni personas inmunodeprimidas.",),
    ),
    SafetyEntry(
        "mariscos", ("camaron", "gamba", "langosta", "langostino", "cangrejo", "jaiba", "vieira", "calamar", "pulpo"),
        "mariscos (camarón, langosta, cangrejo, vieiras)", 63, 145, None,
        "La carne debe quedar perlada y opaca (las vieiras, blancas y firmes).",
        "1-2 días en refrigeración",
    ),
    SafetyEntry(
        "moluscos", ("almeja", "mejillon", "ostion", "ostra"), "almejas, mejillones y ostiones", None, None, None,
        "Cocina hasta que las conchas se abran y desecha las que no abran.", "Vivos: 1-2 días en refrigeración, sin agua",
        ("Los ostiones crudos tienen riesgo de Vibrio; no se recomiendan para grupos vulnerables.",),
    ),
    SafetyEntry(
        "huevo_platillos", ("platillo con huevo", "tortilla de huevo", "quiche", "flan", "frittata", "natilla", "budin", "relleno con huevo", "capeado"),
        "platillos con huevo", 71, 160, None, "Cocina hasta que el centro esté firme y alcance la temperatura.",
    ),
    SafetyEntry(
        "huevo", ("huevo", "huevos", "yema", "clara"), "huevos", 71, 160, None,
        "Cocina hasta que yema y clara estén firmes; en preparaciones con huevo, 71 °C (160 °F).",
        "Huevos crudos con cáscara: 3-5 semanas en refrigeración",
        ("Para preparaciones con huevo crudo (mayonesa casera, tiramisú, mousse) usa huevo pasteurizado.",),
    ),
    SafetyEntry(
        "sobras", ("sobras", "recalentar", "guiso", "guisado", "cazuela", "sopa", "arroz cocido", "comida cocida", "restos"),
        "sobras y guisos", 74, 165, None, "Recalienta hasta 74 °C (165 °F) en todo el alimento; las salsas y sopas, hasta que hiervan.",
        None,
    ),
)

STORAGE_GENERAL = (
    "Refrigera a 4 °C (40 °F) o menos y congela a -18 °C (0 °F). No dejes alimentos perecederos más de 2 horas a "
    "temperatura ambiente (1 hora si hace más de 32 °C / 90 °F). Las sobras cocidas duran 3-4 días refrigeradas; "
    "enfríalas rápido en recipientes poco profundos."
)
REHEATING_GENERAL = (
    "Recalienta las sobras hasta 74 °C (165 °F) en el centro; remueve a media cocción en microondas y deja reposar. "
    "No recalientes la misma porción varias veces."
)
THAWING_GENERAL = (
    "Descongela en el refrigerador, en agua fría (en bolsa cerrada, cambiando el agua cada 30 minutos) o en el "
    "microondas; en los dos últimos casos cocina de inmediato. Nunca descongeles a temperatura ambiente."
)
MEASUREMENT_GENERAL = (
    "Usa un termómetro de cocina en la parte más gruesa del alimento, sin tocar hueso, grasa ni el recipiente. "
    "El color o la apariencia no indican por sí solos que sea seguro."
)
