import requests
import time
import random
import gzip
import re
from io import BytesIO

def recolectar_todas_las_recetas(url_indice):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print(f"Leyendo el índice maestro: {url_indice}")
    respuesta_indice = requests.get(url_indice, headers=headers)
    
    # Búsqueda por fuerza bruta del sub-sitemap en el índice
    sub_sitemaps = re.findall(r'<loc>(.*?)</loc>', respuesta_indice.text)
    sub_sitemaps = [url for url in sub_sitemaps if 'receta' in url.lower()]
            
    print(f"Se encontraron {len(sub_sitemaps)} archivos. Comenzando extracción...\n")
    
    todas_las_recetas = []
    
    for sub_url in sub_sitemaps:
        print(f"Extrayendo enlaces de: {sub_url}")
        try:
            res_sub = requests.get(sub_url, headers=headers)
            
            # Descomprimir a texto puro
            if sub_url.endswith('.gz'):
                archivo_descomprimido = gzip.GzipFile(fileobj=BytesIO(res_sub.content)).read().decode('utf-8', errors='ignore')
            else:
                archivo_descomprimido = res_sub.text
            
            # Buscar TODAS las URLs ignorando el formato XML
            enlaces_encontrados = re.findall(r'<loc>(.*?)</loc>', archivo_descomprimido)
            
            for enlace in enlaces_encontrados:
                if '/receta/' in enlace:
                    todas_las_recetas.append(enlace)
            
            time.sleep(random.uniform(1, 2))
            
        except Exception as e:
            print(f"Error al leer {sub_url}: {e}")
            
    # Eliminar duplicados y guardar
    todas_las_recetas = list(set(todas_las_recetas))
    nombre_archivo = 'lista_recetas.txt'
    
    with open(nombre_archivo, 'w', encoding='utf-8') as archivo:
        for receta in todas_las_recetas:
            archivo.write(receta + '\n')
            
    print(f"\n¡Éxito! Se guardaron {len(todas_las_recetas)} recetas en el archivo '{nombre_archivo}'.")

url_secreta = "https://www.kiwilimon.com/sitemapindex.xml"
recolectar_todas_las_recetas(url_secreta)