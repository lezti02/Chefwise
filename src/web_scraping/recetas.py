from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
import random
import os  # <-- Importante: Añadido para verificar si el archivo existe

def extraer_datos_pagina(page, url):
    datos_receta = {
        "titulo": "", "dificultad": "Desconocida", "tiempo": "Desconocido",
        "ingredientes": "", "preparacion": "", "valoracion": None, "url": url
    }
    
    try:
        # Entramos a la URL y esperamos a que el JS renderice la página
        page.goto(url, wait_until='networkidle', timeout=15000)
    except Exception as e:
        print(f"     Timeout al cargar la página, intentando extraer de todos modos...")
        
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Extracción Visual (Dificultad y Tiempo)
    dificultad_match = soup.find(string=re.compile(r'^\s*(Baja|Media|Alta)\s*$', re.IGNORECASE))
    if dificultad_match:
        datos_receta["dificultad"] = dificultad_match.strip().capitalize()
        
    # Regex para atrapar "20 mins", "1 h", "1 h 30 mins", "2 horas"
    tiempo_match = soup.find(string=re.compile(r'^\s*\d+\s*(h|horas?|mins?)(?:\s*\d+\s*mins?)?\s*$', re.IGNORECASE))
    if tiempo_match:
        datos_receta["tiempo"] = tiempo_match.strip()

    # 2. Extracción Estructurada JSON-LD
    bloques_scripts = soup.find_all('script', type='application/ld+json')
    receta_json = None
    
    for bloque in bloques_scripts:
        try:
            datos = json.loads(bloque.string)
            if isinstance(datos, list):
                for item in datos:
                    if item.get('@type') == 'Recipe':
                        receta_json = item
            elif isinstance(datos, dict):
                if datos.get('@type') == 'Recipe':
                    receta_json = datos
                elif '@graph' in datos:
                    for item in datos['@graph']:
                        if item.get('@type') == 'Recipe':
                            receta_json = item
        except:
            continue

    # 3. Formateo de los datos para CSV
    if receta_json:
        datos_receta["titulo"] = receta_json.get('name', soup.find('h1').text.strip() if soup.find('h1') else '')
        
        # Unimos los ingredientes con " | " para no romper las celdas de Excel
        ings = receta_json.get('recipeIngredient', [])
        datos_receta["ingredientes"] = " | ".join(ings)
        
        instrucciones = receta_json.get('recipeInstructions', [])
        pasos = []
        for paso in instrucciones:
            if isinstance(paso, dict):
                texto_paso = paso.get('text', '')
            elif isinstance(paso, str):
                texto_paso = paso
            else:
                texto_paso = ""
                
            # Limpieza avanzada de HTML y publicidad en la preparación
            s = BeautifulSoup(texto_paso, 'html.parser')
            
            # Destruimos etiquetas div y a (donde viven los botones de compra)
            for etiqueta_basura in s.find_all(['div', 'a']):
                etiqueta_basura.decompose()
                
            texto_limpio = s.get_text(separator=" ").strip()
            
            # Borramos la frase "Comprar AQUÍ" si llega a sobrevivir
            texto_limpio = re.sub(r'Comprar AQU[ÍI].*', '', texto_limpio, flags=re.IGNORECASE)
            
            # Aplanamos los espacios gigantes y saltos de línea múltiples
            texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
            
            if texto_limpio:
                pasos.append(texto_limpio)
                
        datos_receta["preparacion"] = " | ".join(pasos)
                
        rating = receta_json.get('aggregateRating', {})
        if rating:
            datos_receta["valoracion"] = rating.get('ratingValue')

    return datos_receta

def compilar_dataset(archivo_urls, archivo_csv, limite=15):
    # Leer las URLs del archivo de texto
    try:
        with open(archivo_urls, 'r', encoding='utf-8') as f:
            urls = [linea.strip() for linea in f.readlines() if linea.strip()]
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {archivo_urls}")
        return

    urls = urls[:limite]
    recetas_guardadas = 0  # <-- Reemplazamos la lista por un contador
    
    print(f"Iniciando extracción de {len(urls)} recetas...")
    
    # Abrimos Playwright UNA sola vez
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Bloquear imágenes para acelerar la carga de la página
        context = browser.new_context()
        context.route("**/*.{png,jpg,jpeg,webp,gif,svg}", lambda route: route.abort())
        page = context.new_page()
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Extrayendo: {url}")
            try:
                # Corregido un pequeño typo de la versión anterior (extraer_data =)
                datos = extraer_datos_pagina(page, url) 
                
                if datos["titulo"] and datos["ingredientes"]:  
                    # Crear un DataFrame temporal solo con esta receta
                    df_temp = pd.DataFrame([datos])
                    
                    # Verificamos si el archivo ya existe para saber si escribir los encabezados
                    archivo_existe = os.path.isfile(archivo_csv)
                    
                    # Guardar anexando al archivo ('a'). Si es la primera vez (no existe), añade headers
                    df_temp.to_csv(archivo_csv, mode='a', header=not archivo_existe, index=False, encoding='utf-8-sig')
                    
                    recetas_guardadas += 1
                else:
                    print("    No se detectaron ingredientes o título.")
                    
                # Pausa aleatoria para imitar comportamiento humano
                time.sleep(random.uniform(0.3,0.5))
            except Exception as e:
                print(f"    Error inesperado: {e}")
                
        browser.close()
    
    print(f"\n¡Éxito! Se procesó la lista. Total guardadas en esta sesión: {recetas_guardadas} recetas en '{archivo_csv}'.")

# Ejecutamos el compilador
compilar_dataset('lista_recetas.txt', 'dataset_recetas.csv', limite=1500)