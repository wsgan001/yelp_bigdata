import ast
import re
import sqlite3
import time

from mpi4py import MPI
from queue import PriorityQueue

comm = MPI.COMM_WORLD
size = MPI.COMM_WORLD.Get_size()
rank = MPI.COMM_WORLD.Get_rank()
name = MPI.Get_processor_name()

JSON_PATH = '/mnt/storage/metadata.json'
DB_PATH = '/mnt/storage/metadata.db'
NUMROWS = 9430088
STEP = int(NUMROWS/size) + 1

TOP_K_VALUE = 10

ASIN_RE = re.compile(r"'asin': '(\w+)'")

def chunk_data(json_data):   
    child_rank = 1 % size
    line = json_data.readline()
    while line:
        chunk_asin = []
        counter = 0

        while counter <= STEP and line:
            asin = ASIN_RE.search(line).group(1)
            #data = ast.literal_eval(line)
            #asin = data['asin']
            chunk_asin.append(asin)
            counter += 1
            line = json_data.readline()

        if child_rank != 0:
            comm.send(chunk_asin, dest=child_rank, tag=7)
            print('chunk {} sent!'.format(child_rank))
        
        # if child_rank == 0:
        #     break
        child_rank = (child_rank + 1) % size

    return chunk_asin

if __name__ == '__main__':
    
    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()
    
    if rank == 0:
        print(time.time())

        json_data = open(JSON_PATH, 'r')
    
        chunk_asin = chunk_data(json_data)
        
        json_data.close()
    
    else:
        chunk_asin = comm.recv(source=0, tag=7)


    outlist = PriorityQueue(maxsize=TOP_K_VALUE)

    for i, asin in enumerate(chunk_asin):
   
        query = c.execute('''select count(asin2) from ALSOVIEWED where asin=?;''', (asin,))

        count = query.fetchone()[0]

        pair_info = (count, asin)

        if not outlist.full():
            outlist.put(pair_info)
        else:
            curr_min_info = outlist.get()
            if count >= curr_min_info[0]:
                outlist.put(pair_info)
            else:
                outlist.put(curr_min_info)

    outrv = []
    while not outlist.empty():
        outrv.append(outlist.get())
    print(outrv, "in machine", rank)

    gathered_chunks = comm.gather(outrv, root=0)

    if rank == 0:
        print(time.time())
        print(gathered_chunks)       

    conn.close()
