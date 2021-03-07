import logging
import os
from concurrent.futures import ThreadPoolExecutor
import datetime
from itertools import chain, islice
from functools import partial
import pickle

import requests


class MeliApiClient:

    def __init__(self):
        # url para buscar por query string
        self.SITES_URL = ("https://api.mercadolibre.com/sites/MLA/"
                   "search?limit={limit}&offset={offset}&q={query}")
        self.ITEMS_URL = ("https://api.mercadolibre.com/items/{}")
        # strings para el parametro query de SITES
        self.SITES_Q_1 = ['tv%204k', 'microondas', 'phone', 
                        'celular', 'auto%toyota', 'cablehdmi', 
                        'laptop', 'disco%externo', 'kindle',
                        'amplificador', 'consola%yamaha', 'proyector',
                        'mochila', 'heladera', 'extractor'
                        'tablet', 'parlante', 'sintetizador',
                        'aspiradora','aspiradorarobot', 'auriculares', 'cargador',
                        'ventilador', 'bicicleta', 'drone',
                        'aireacondicionado', 'playstation',
                        'termotanque', 'hidrolavadora',
                        'estufa', 'parrillaagas', 'thermomix']
    def sites_url_query_gen(self,
                            limit=50,
                            steps=22):
        for query in self.SITES_Q_1:
            logging.info(query)
        # generador que forma la url de SITES para hacer la request
            for step in range(steps):
                params = {
                    'query': query,
                    'limit': limit,
                    'offset': limit*step
                }
                nurl = self.SITES_URL.format(**params)
                yield nurl

    def items_url_query_gen(self, items):
        # generador para formar la url de items
        for item in items:
            yield self.ITEMS_URL.format(item)
        
    def _batch_generator(self, iterable, size):
        sourceiter = iter(iterable)
        while True:
            batchiter = islice(sourceiter, size)
            yield chain(
                    [next(batchiter)], 
                    batchiter)


    def thread_wrapper_requests(self, batch_size, url_gen):
        for batch_urls in self._batch_generator(
                    url_gen(),
                    batch_size
                    ):
        
            with ThreadPoolExecutor() as executor:
                r = executor.map(requests.get, batch_urls, timeout=60)
            yield r

    def process_todict(self, raw_data, key):
        master_dict = {}
        count = 0
        for ri in raw_data:
            for request in ri:
                if request.ok:
                    data = request.json().get(key)
    #            if data:
                    for i in range(len(data)):
                        try:
                            count += 1
                            if key == 'results':
                                master_dict[data[i].get('id')] = data[i]
                            else:
                                master_dict[request.json().get('id')] = data
                        except IndexError as e:                            
                            logging.warning(f"{e} in {i}")
                        except KeyError as e:
                            logging.warning(f"{e} in {i}")
                        except AttributeError as e:
                            logging.warning(f"{e} in {i}")
        return master_dict, count
    
if __name__ == '__main__':
    now = (datetime.datetime.now()
       .isoformat()
       .replace(':', '_')
       .split('.')[0])
    logging.basicConfig(filename=f'logs/api_meli_{now}', 
                    level=logging.INFO)
    # Creo instancia
    mac = MeliApiClient()
    # request de url sites
    r = mac.thread_wrapper_requests(50, mac.sites_url_query_gen)
    sites_dict, count_sites = mac.process_todict(r, 'results')
    logging.info(f"{count_sites} results")
    # guardo resultados en un diccionario
    with open(f'results/meli_sites_api_data_{now}.p', 'wb') as f:
        pickle.dump(sites_dict, f)
    logging.info("Finished sites request")
    
    # items stage
    r2 = mac.thread_wrapper_requests(
            50,
            # funcion parcial, para luego darle otro argumento 
            # en el wrapper de concurrencia
            partial(mac.items_url_query_gen, sites_dict)
            )
    items_dict, count_items = mac.process_todict(r2, 'id')
    logging.info(f"{count_items} results")
    # guardo resultados en un diccionario
    with open(f'results/meli_items_api_data_{now}.p', 'wb') as f:
        pickle.dump(items_dict, f)
    logging.info("Finished sites request")
