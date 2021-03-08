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
        self.ITEMSMETRICS_URL = ("https://api.mercadolibre.com/items/"
                                 "visits?ids={item_ids_csv}&"
                                 "date_from={date_from}&date_to={date_to}")
        self.USERMETRICS_URL = ("https://api.mercadolibre.com/users/{user_id}/"
                                "items_visits?date_from={date_from}&date_to={date_to}")
        date_to = datetime.datetime.now()
        self.DATE_FROM = (date_to - datetime.timedelta(30)).isoformat()
        self.DATE_TO = date_to.isoformat()
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
        
    def items_metrics_url_query_gen(self, items):
        for item in items:
            params = {'item_ids_csv': item,
                     'date_from': self.DATE_FROM,
                     'date_to': self.DATE_TO}
            yield self.ITEMSMETRICS_URL.format(**params)

    def user_metrics_url_query_gen(self, user_ids):
        for user in users:
            params = {'user_id': user,
                      'date_from': self.DATE_FROM,
                      'date_to': self.DATE_TO}

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
                            elif key == 'user_id':
                                master_dict[request.json().get('user_id')] = data
                            elif key == 'item_id':
                                master_dict[request.json().get('item_id')] = data
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
    logging.basicConfig(filename=f'logs/api_meli_{now}.log', 
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
            partial(mac.items_url_query_gen, sites_dict)
            )
    items_dict, count_items = mac.process_todict(r2, 'id')
    logging.info(f"{count_items} results")
    # guardo resultados en un diccionario
    with open(f'results/meli_items_api_data_{now}.p', 'wb') as f:
        pickle.dump(items_dict, f)
    logging.info("Finished items request")

    # items metrics
    r3 = mac.thread_wrapper_requests(
            50,
            partial(mac.items_metrics_url_query_gen, sites_dict)
            )
    items_metrics_dict, count_item_metrics = mac.process_todict(r3, 'item_id')
    logging.info(f"{count_item_metrics} results")
    with open(f'results/meli_items_metrics_api_data_{now}.p', 'wb') as f:
        pickle.dump(items_metrics_dict, f)
    logging.info("Finished item metrics request")

    # user metrics
    seller_ids = (item[k].get('seller_id') for k in items_metrics_dict)
    r4 = mac.thread_wrapper_requests(
            50,
            partial(mac.user_metrics_url_query_gen,
                    seller_ids))
    seller_metrics_dict, count_seller_metrics = mac.process_todict(r4, 'user_id')
    with open(f'results/meli_seller_metrics_api_data_{now}.p', 'wb') as f:
        pickle.dump(seller_metrics_dict, f)
    logging.info("Finished seller metrics request")

