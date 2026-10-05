"""Base curada de sustituciones culinarias, organizada por la FUNCIÓN del ingrediente.

Proporciones estándar de cocina casera. `ratio_factor` multiplica la cantidad
original cuando la equivalencia es directa en la misma unidad; None cuando la
proporción se expresa "por pieza" o cambia de unidad (va en `ratio`).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SubOption:
    substitute: str
    ratio: str
    instructions: str
    flavor_changes: str
    texture_changes: str
    ratio_factor: float | None = None
    allergens: tuple[str, ...] = ()  # ids de allergens.ALLERGENS
    vegan: bool = True
    alcohol: bool = False
    good_for: tuple[str, ...] = ()  # usos/propiedades (sin acentos)


@dataclass(frozen=True)
class SubEntry:
    keys: tuple[str, ...]
    label: str
    function: str
    options: tuple[SubOption, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


SUBSTITUTIONS: tuple[SubEntry, ...] = (
    SubEntry(
        ("huevo", "huevos"), "huevo",
        "Aglutinante, humedad y estructura; en horneados también ayuda a leudar; en capeados da adherencia y esponjosidad.",
        (
            SubOption("linaza molida + agua", "1 cda de linaza molida + 3 cdas de agua por huevo",
                      "Mezcla y deja reposar 10 minutos hasta que espese.", "Ligero sabor a nuez.",
                      "Miga más densa y húmeda; no monta.", good_for=("aglutinante", "horneado", "galletas", "panque", "hamburguesas")),
            SubOption("chía molida + agua", "1 cda de chía + 3 cdas de agua por huevo",
                      "Reposa 10 minutos; muélela si no quieres puntos negros.", "Casi neutro.",
                      "Más densa y húmeda.", good_for=("aglutinante", "horneado", "galletas")),
            SubOption("puré de manzana sin azúcar o plátano maduro", "¼ de taza (60 g) por huevo",
                      "Añade ¼ de cdita extra de polvo para hornear por huevo sustituido.", "Dulzor y sabor frutal.",
                      "Más húmedo y denso.", good_for=("humedad", "horneado", "dulce", "panque", "brownies", "hotcakes")),
            SubOption("aquafaba (líquido de garbanzos de lata)", "3 cdas por huevo (2 cdas por clara)",
                      "Bátela como clara si buscas aire; úsala fría.", "Neutro una vez cocido.",
                      "Ligera; puede montar como merengue.", good_for=("clara", "merengue", "capeado", "ligereza", "batido")),
            SubOption("agua mineral con gas muy fría + 1 cda de maicena", "¼ de taza de agua con gas + 1 cda de maicena por huevo",
                      "Solo para capeados/rebozados: mezcla justo antes de freír.", "Neutro.",
                      "Capeado más ligero y crujiente, algo menos dorado.", good_for=("capeado", "rebozado", "frito")),
        ),
        ("En recetas donde el huevo es protagonista (flan, omelette, merengue) no hay sustituto equivalente.",),
    ),
    SubEntry(
        ("mantequilla",), "mantequilla",
        "Grasa que da sabor, ternura y dorado; en masas cremadas atrapa aire.",
        (
            SubOption("aceite vegetal neutro", "¾ de la cantidad de mantequilla", "Úsalo derretido/líquido; no sirve para cremar con azúcar.",
                      "Pierde el sabor a mantequilla.", "Miga más húmeda y compacta; galletas más planas.",
                      ratio_factor=0.75, good_for=("horneado", "panque", "saltear", "muffins")),
            SubOption("aceite de coco sólido", "1:1", "Úsalo a la misma temperatura que la mantequilla de la receta.",
                      "Sabor a coco (usa el refinado si no lo quieres).", "Similar; algo más quebradizo.",
                      ratio_factor=1.0, good_for=("horneado", "galletas", "cremar")),
            SubOption("margarina vegetal en barra", "1:1", "Revisa la etiqueta: algunas contienen suero de leche.",
                      "Menos sabor.", "Similar.", ratio_factor=1.0, good_for=("horneado", "cremar", "untar")),
            SubOption("ghee (mantequilla clarificada)", "1:1", "Ideal para saltear a fuego alto.",
                      "Más tostado.", "Similar; menos agua.", ratio_factor=1.0, allergens=("lacteos",), vegan=False,
                      good_for=("saltear", "freir")),
        ),
        ("En hojaldres y masas laminadas la mantequilla no tiene sustituto equivalente.",),
    ),
    SubEntry(
        ("leche",), "leche",
        "Líquido con grasa y proteína: hidrata, suaviza y ayuda al dorado.",
        (
            SubOption("bebida de soya sin azúcar", "1:1", "Usa la versión natural sin endulzar.", "Ligero sabor a soya.",
                      "Muy similar (proteína parecida).", ratio_factor=1.0, allergens=("soya",), good_for=("horneado", "salsas", "bechamel")),
            SubOption("bebida de avena sin azúcar", "1:1", "Si hay celiaquía, que sea avena certificada sin gluten.",
                      "Dulzor suave.", "Algo más espesa.", ratio_factor=1.0, good_for=("horneado", "cafe", "avena")),
            SubOption("bebida de almendra sin azúcar", "1:1", "", "Sabor a almendra.", "Más ligera.",
                      ratio_factor=1.0, allergens=("frutos-secos",), good_for=("batidos", "horneado")),
            SubOption("leche evaporada + agua", "½ de leche evaporada + ½ de agua", "", "Ligeramente acaramelado.",
                      "Igual.", ratio_factor=1.0, allergens=("lacteos",), vegan=False, good_for=("salsas", "postres")),
        ),
    ),
    SubEntry(
        ("crema", "crema para batir", "nata", "crema de leche", "media crema"), "crema",
        "Grasa láctea que da cremosidad y cuerpo; la de batir monta.",
        (
            SubOption("leche evaporada", "1:1", "No dejes que hierva fuerte para que no se corte.", "Menos rica, leve caramelo.",
                      "Más ligera; no monta.", ratio_factor=1.0, allergens=("lacteos",), vegan=False, good_for=("salsas", "sopas", "cremosidad")),
            SubOption("yogur griego natural", "1:1", "Añádelo al final y fuera del fuego.", "Ácido.", "Cremosa y espesa.",
                      ratio_factor=1.0, allergens=("lacteos",), vegan=False, good_for=("salsas frias", "aderezos", "cremosidad")),
            SubOption("leche o crema de coco entera", "1:1", "Agita la lata; para montar, refrigera la crema de coco una noche.",
                      "Sabor a coco.", "Cremosa; la crema de coco fría monta.", ratio_factor=1.0, good_for=("curry", "postres", "batido", "sopas")),
            SubOption("anacardos remojados licuados", "½ taza de anacardos + ½ taza de agua por taza de crema",
                      "Remoja 2 h (o 15 min en agua hirviendo) y licúa hasta que quede liso.", "Suave a nuez.",
                      "Muy cremosa; no monta.", allergens=("frutos-secos",), good_for=("salsas", "cremosidad")),
        ),
    ),
    SubEntry(
        ("crema agria", "crema acida"), "crema agria",
        "Grasa con acidez: cremosidad y frescura.",
        (
            SubOption("yogur griego natural", "1:1", "", "Algo más ácido.", "Similar.", ratio_factor=1.0,
                      allergens=("lacteos",), vegan=False, good_for=("aderezos", "horneado", "tacos")),
            SubOption("crema + jugo de limón", "1 taza de crema + 1 cda de jugo de limón", "Mezcla y deja reposar 10 minutos.",
                      "Similar.", "Similar.", ratio_factor=1.0, allergens=("lacteos",), vegan=False, good_for=("aderezos", "salsas")),
        ),
    ),
    SubEntry(
        ("suero de leche", "buttermilk", "leche agria", "jocoque liquido"), "suero de leche",
        "Líquido ácido que reacciona con el bicarbonato y da miga tierna.",
        (
            SubOption("leche + jugo de limón o vinagre", "1 taza de leche + 1 cda de jugo de limón o vinagre",
                      "Deja reposar 5-10 minutos hasta que se corte un poco.", "Igual de ácido.", "Igual.",
                      ratio_factor=1.0, allergens=("lacteos",), vegan=False, good_for=("horneado", "hotcakes", "pollo frito")),
            SubOption("bebida de soya + vinagre", "1 taza de bebida de soya + 1 cda de vinagre", "Reposa 10 minutos.",
                      "Similar.", "Similar.", ratio_factor=1.0, allergens=("soya",), good_for=("horneado", "hotcakes")),
        ),
    ),
    SubEntry(
        ("harina", "harina de trigo", "harina todo uso"), "harina de trigo",
        "Da estructura (gluten) en horneados, espesa salsas y forma la capa de capeados y rebozados.",
        (
            SubOption("fécula de maíz (maicena) para espesar", "la mitad: 1 cda de maicena por 2 cdas de harina",
                      "Disuélvela en líquido frío antes de añadirla y hierve 1-2 minutos.", "Neutro.",
                      "Salsa más brillante y translúcida.", ratio_factor=0.5, good_for=("espesar", "salsas", "sopas", "gravy")),
            SubOption("harina de arroz", "1:1", "Ideal para capear y freír.", "Neutro.", "Más crujiente; sin elasticidad.",
                      ratio_factor=1.0, good_for=("capeado", "rebozado", "frito", "sin gluten")),
            SubOption("mezcla de harinas sin gluten con goma xantana", "1:1 (por peso)", "Deja reposar la masa 15-30 min.",
                      "Ligeramente distinto según la mezcla.", "Miga más frágil y menos esponjosa.",
                      ratio_factor=1.0, good_for=("horneado", "pasteles", "galletas", "sin gluten")),
        ),
        ("En panes de levadura no hay sustituto sin gluten que dé el mismo resultado.",),
    ),
    SubEntry(
        ("maicena", "fecula de maiz", "almidon de maiz"), "fécula de maíz",
        "Espesante (y en capeados, crujencia).",
        (
            SubOption("harina de trigo", "el doble: 2 cdas de harina por 1 cda de maicena", "Cocina 2-3 minutos más para quitar el sabor a crudo.",
                      "Algo a harina si se cuece poco.", "Salsa opaca.", ratio_factor=2.0, allergens=("gluten",), good_for=("espesar", "salsas")),
            SubOption("fécula de papa, tapioca o arrurruz", "1:1", "Añádela al final; no la hiervas mucho tiempo.",
                      "Neutro.", "Similar o más elástica (tapioca).", ratio_factor=1.0, good_for=("espesar", "salsas", "capeado")),
        ),
    ),
    SubEntry(
        ("pan molido", "pan rallado", "empanizador"), "pan molido",
        "Cobertura crujiente y aglutinante en albóndigas/hamburguesas.",
        (
            SubOption("avena en hojuelas molida", "1:1", "Para celiaquía, avena certificada sin gluten.", "Ligeramente dulce.",
                      "Algo menos crujiente.", ratio_factor=1.0, good_for=("empanizar", "albondigas", "aglutinante")),
            SubOption("hojuelas de maíz trituradas", "1:1", "Revisa la etiqueta si evitas gluten (algunas llevan malta).",
                      "Ligeramente dulce.", "Muy crujiente.", ratio_factor=1.0, good_for=("empanizar", "frito", "horno")),
            SubOption("harina de almendra", "1:1", "", "Sabor a almendra.", "Dora más rápido.", ratio_factor=1.0,
                      allergens=("frutos-secos",), good_for=("empanizar", "sin gluten")),
        ),
    ),
    SubEntry(
        ("polvo para hornear", "royal", "levadura quimica"), "polvo para hornear",
        "Leudante químico: produce gas al mojarse y al calentarse.",
        (
            SubOption("bicarbonato + cremor tártaro", "¼ cdita de bicarbonato + ½ cdita de cremor tártaro por cada cdita",
                      "Hornea en cuanto mezcles.", "Neutro.", "Similar.", good_for=("horneado",)),
            SubOption("bicarbonato + yogur o suero de leche", "¼ cdita de bicarbonato + ½ taza de yogur/suero por cada cdita",
                      "Reduce ½ taza de otro líquido de la receta.", "Ligera acidez.", "Similar.",
                      allergens=("lacteos",), vegan=False, good_for=("horneado", "hotcakes")),
        ),
    ),
    SubEntry(
        ("bicarbonato", "bicarbonato de sodio"), "bicarbonato",
        "Leudante que necesita un ácido de la receta (yogur, suero, limón, cacao natural).",
        (
            SubOption("polvo para hornear", "el triple: 3 cditas de polvo por 1 cdita de bicarbonato",
                      "Reduce un poco la sal.", "Puede quedar algo amargo/salado.", "Menos dorado.", ratio_factor=3.0, good_for=("horneado",)),
        ),
    ),
    SubEntry(
        ("levadura", "levadura seca", "levadura fresca", "levadura instantanea"), "levadura",
        "Leudante biológico: fermenta y da volumen y sabor a la masa.",
        (
            SubOption("levadura fresca (en lugar de seca activa)", "3 g de fresca por cada 1 g de seca", "Desmorónala en el líquido tibio.",
                      "Igual.", "Igual.", good_for=("pan",)),
            SubOption("levadura instantánea (en lugar de seca activa)", "1:1 o un 25 % menos", "Se mezcla directo con la harina, sin activar.",
                      "Igual.", "Igual; levado algo más rápido.", ratio_factor=1.0, good_for=("pan", "pizza")),
        ),
        ("El polvo para hornear no sustituye a la levadura en panes: el resultado sería otro tipo de masa.",),
    ),
    SubEntry(
        ("grenetina", "gelatina sin sabor", "gelatina en polvo"), "grenetina",
        "Gelificante de origen animal: cuaja en frío.",
        (
            SubOption("agar agar en polvo", "1 cdita de agar por cada cda de grenetina en polvo",
                      "Debe hervir 1-2 minutos para activarse; cuaja a temperatura ambiente.", "Neutro.",
                      "Más firme y quebradizo, menos elástico.", good_for=("gelatinas", "postres", "vegano")),
        ),
        ("Las frutas crudas como piña, kiwi o papaya impiden que cuaje la grenetina.",),
    ),
    SubEntry(
        ("azucar", "azucar blanca"), "azúcar",
        "Endulza, carameliza, retiene humedad y ayuda a la textura en horneados.",
        (
            SubOption("miel", "¾ de taza por taza de azúcar", "Reduce ¼ de taza de líquido y baja el horno unos 15 °C (dora más rápido).",
                      "Sabor a miel.", "Más húmedo y denso.", ratio_factor=0.75, vegan=False, good_for=("horneado", "aderezos")),
            SubOption("azúcar morena o mascabado", "1:1", "", "Notas de melaza/caramelo.", "Más húmedo.", ratio_factor=1.0,
                      good_for=("galletas", "horneado", "salsas")),
            SubOption("piloncillo rallado", "1:1", "Rállalo fino o disuélvelo en el líquido.", "Sabor a caramelo intenso.",
                      "Más húmedo.", ratio_factor=1.0, good_for=("postres mexicanos", "cafe de olla", "salsas")),
        ),
    ),
    SubEntry(
        ("miel", "miel de abeja"), "miel",
        "Endulzante líquido: humedad, dorado y sabor.",
        (
            SubOption("jarabe de agave", "1:1", "", "Más neutro.", "Igual.", ratio_factor=1.0, good_for=("aderezos", "postres", "vegano")),
            SubOption("jarabe de maple", "1:1", "", "Sabor a maple.", "Algo más líquido.", ratio_factor=1.0, good_for=("hotcakes", "glaseados")),
            SubOption("azúcar + líquido", "1¼ tazas de azúcar + ¼ de taza de líquido por taza de miel", "", "Más neutro.",
                      "Menos húmedo.", good_for=("horneado",)),
        ),
    ),
    SubEntry(
        ("cerveza",), "cerveza",
        "En capeados aporta burbujas (ligereza y crujencia); en guisos, sabor y acidez.",
        (
            SubOption("agua mineral con gas muy fría", "1:1", "Para capeados: mézclala justo antes de freír.",
                      "Pierde el amargor de la cerveza.", "Capeado igual de ligero.", ratio_factor=1.0,
                      good_for=("capeado", "rebozado", "frito", "sin alcohol", "sin gluten")),
            SubOption("caldo de pollo o de verduras", "1:1", "Para guisos y carnes; ajusta la sal.", "Más salado y menos amargo.",
                      "Igual.", ratio_factor=1.0, vegan=False, good_for=("guisos", "carnes", "frijoles")),
            SubOption("cerveza sin alcohol", "1:1", "", "Muy similar.", "Igual.", ratio_factor=1.0, allergens=("gluten",),
                      good_for=("capeado", "guisos", "sin alcohol")),
        ),
    ),
    SubEntry(
        ("vino blanco",), "vino blanco",
        "Acidez y aroma para desglasar y en salsas.",
        (
            SubOption("caldo + jugo de limón o vinagre", "1 taza de caldo + 1 cda de jugo de limón o vinagre de vino",
                      "", "Menos afrutado.", "Igual.", ratio_factor=1.0, vegan=False, good_for=("salsas", "risotto", "mariscos", "sin alcohol")),
            SubOption("jugo de uva blanca + vinagre", "1 taza de jugo + 1 cda de vinagre", "Útil en salsas dulces.",
                      "Más dulce.", "Igual.", ratio_factor=1.0, good_for=("salsas", "sin alcohol")),
        ),
    ),
    SubEntry(
        ("vino tinto",), "vino tinto",
        "Acidez, color y profundidad en guisos y salsas.",
        (
            SubOption("caldo de res + vinagre balsámico", "1 taza de caldo + 1 cda de vinagre balsámico", "", "Menos complejo.",
                      "Igual.", ratio_factor=1.0, vegan=False, good_for=("guisos", "carnes", "sin alcohol")),
            SubOption("jugo de uva tinta sin azúcar + vinagre", "1 taza + 1 cda de vinagre de vino", "", "Más dulce.", "Igual.",
                      ratio_factor=1.0, good_for=("salsas", "sin alcohol")),
        ),
    ),
    SubEntry(
        ("brandy", "cognac", "coñac", "ron", "licor", "tequila", "whisky", "jerez"), "licor",
        "Aroma; en capeados, el alcohol evapora rápido y da crujencia.",
        (
            SubOption("jugo de manzana o de uva", "1:1", "Para postres y salsas.", "Más dulce, sin notas alcohólicas.",
                      "Igual.", ratio_factor=1.0, good_for=("postres", "salsas", "sin alcohol")),
            SubOption("agua mineral con gas", "1:1", "En capeados.", "Neutro.", "Igual de crujiente.", ratio_factor=1.0,
                      good_for=("capeado", "rebozado", "sin alcohol")),
            SubOption("omitirlo", "—", "Repón el volumen con el líquido principal de la receta.", "Menos aroma.", "Igual.",
                      good_for=("sin alcohol",)),
        ),
    ),
    SubEntry(
        ("jugo de limon", "limon", "zumo de limon"), "jugo de limón",
        "Acidez que equilibra y realza sabores.",
        (
            SubOption("jugo de lima", "1:1", "", "Muy similar.", "Igual.", ratio_factor=1.0, good_for=("aderezos", "marinadas")),
            SubOption("vinagre de manzana o blanco", "la mitad de la cantidad", "", "Más agresivo; sin aroma cítrico.", "Igual.",
                      ratio_factor=0.5, good_for=("aderezos", "marinadas", "suero")),
        ),
        ("En conservas no cambies el ácido indicado: la acidez es parte de la seguridad.",),
    ),
    SubEntry(
        ("vinagre",), "vinagre",
        "Acidez.",
        (
            SubOption("jugo de limón", "1:1", "", "Cítrico.", "Igual.", ratio_factor=1.0, good_for=("aderezos", "marinadas")),
        ),
        ("En conservas y encurtidos no sustituyas el vinagre: su acidez es parte de la seguridad.",),
    ),
    SubEntry(
        ("caldo de pollo", "consome de pollo"), "caldo de pollo",
        "Líquido con sabor y sal.",
        (
            SubOption("caldo de verduras", "1:1", "", "Más vegetal.", "Igual.", ratio_factor=1.0, good_for=("sopas", "arroz", "vegano")),
            SubOption("agua + consomé en polvo o cubo", "1 cubo por cada 2 tazas de agua (según el envase)", "Reduce la sal de la receta.",
                      "Más salado.", "Igual.", vegan=False, good_for=("sopas", "arroz")),
        ),
    ),
    SubEntry(
        ("queso parmesano", "parmesano"), "queso parmesano",
        "Sabor salado y umami.",
        (
            SubOption("queso añejo o cotija", "1:1", "", "Menos intenso.", "Similar.", ratio_factor=1.0, allergens=("lacteos",),
                      vegan=False, good_for=("pastas", "gratinar")),
            SubOption("levadura nutricional", "⅓ de la cantidad", "", "Umami, ligeramente a nuez.", "No gratina.",
                      ratio_factor=0.33, good_for=("pastas", "vegano")),
        ),
    ),
    SubEntry(
        ("mayonesa",), "mayonesa",
        "Grasa emulsionada: cremosidad y untuosidad.",
        (
            SubOption("yogur griego natural", "1:1", "Añade unas gotas de limón y sal.", "Más ácido.", "Menos untuoso.",
                      ratio_factor=1.0, allergens=("lacteos",), vegan=False, good_for=("aderezos", "ensaladas", "tacos")),
            SubOption("aguacate machacado", "1:1", "Prepáralo al momento (se oxida).", "Sabor a aguacate.", "Cremoso.",
                      ratio_factor=1.0, good_for=("sandwich", "tacos", "vegano")),
        ),
    ),
    SubEntry(
        ("yogur", "yogurt", "yogur natural"), "yogur natural",
        "Acidez y cremosidad; en horneados aporta humedad.",
        (
            SubOption("crema agria", "1:1", "", "Más grasa.", "Similar.", ratio_factor=1.0, allergens=("lacteos",), vegan=False,
                      good_for=("aderezos", "horneado")),
            SubOption("yogur de soya o de coco natural", "1:1", "", "Ligero sabor de la base.", "Similar.", ratio_factor=1.0,
                      allergens=("soya",), good_for=("horneado", "vegano")),
        ),
    ),
    SubEntry(
        ("cebolla",), "cebolla",
        "Base aromática dulce al cocinarse.",
        (
            SubOption("chalota (echalote)", "1:1 en volumen", "", "Más suave y dulce.", "Igual.", ratio_factor=1.0, good_for=("salsas", "saltear")),
            SubOption("poro (puerro) o cebollín", "1:1 en volumen", "Usa la parte blanca del poro.", "Más suave.", "Igual.",
                      ratio_factor=1.0, good_for=("sopas", "saltear")),
            SubOption("cebolla en polvo", "1 cda por cebolla mediana", "", "Menos dulce.", "Sin textura.", good_for=("sazonar", "carnes")),
        ),
    ),
    SubEntry(
        ("ajo", "diente de ajo"), "ajo",
        "Aromático.",
        (
            SubOption("ajo en polvo", "⅛ de cdita por diente", "", "Menos fresco.", "Sin textura.", good_for=("sazonar",)),
        ),
    ),
    SubEntry(
        ("chile", "jalapeno", "serrano", "chile jalapeno", "chile serrano"), "chile fresco",
        "Picor y aroma.",
        (
            SubOption("hojuelas de chile o chile en polvo", "¼ de cdita por chile", "Añade poco a poco y prueba.", "Más tostado.",
                      "Sin textura.", good_for=("sazonar", "picante")),
            SubOption("pimiento morrón", "1:1 en volumen", "Para el sabor sin picor.", "Dulce, sin picor.", "Igual.",
                      ratio_factor=1.0, good_for=("sin picante", "ninos")),
        ),
        ("Los chiles varían mucho en picor: ajusta al gusto.",),
    ),
)
