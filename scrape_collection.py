#!/usr/bin/env python

import urllib.request as urllib2
import requests
import argparse
import io
import json
import zipfile
from PIL import Image

import path

import termcolor as tc
import util
import subprocess

def download_thumb(mid, fname):
    """ save thumb of model id to fname """
    print(tc.colored('downloading '+fname, 'green'))
    url = "https://3dwarehouse.sketchup.com/warehouse/getbinary?subjectId="+mid
    url = url + "&subjectClass=collection&name=bot_st"
    print(url)
    r = requests.get(url)
    print(r.url)
    img_data = urllib2.urlopen(r.url).read()
    img = Image.open(io.BytesIO(img_data))
    img.save(fname)

def get_model_ids(collection_url):
    """ get download urls for collection """
    model_ids = []
    url = collection_url
    print('Scraping model ids from %s'%(url))
    response = urllib2.urlopen(url).read().decode('utf8')
    data = json.loads(response)['entries']
    for model in data:
        model_ids.append(model['id'])
    return model_ids

def generate_sdf(mdir,mid):
    config_string = """<?xml version="1.0"?>
<model>
  <name>"""+mid+"""</name>
  <version>1.0</version>
  <sdf version="1.5">model.sdf</sdf>
</model>"""

    sdf_string = """<?xml version="1.0" ?>
<sdf version="1.5">
  <model name=\""""+mid+"""\">
    <link name="link">
      <visual name="visual">
        <geometry>
          <mesh>
            <scale>1 1 1</scale>
            <uri>model://"""+mid+"""/model.dae</uri>
          </mesh>
        </geometry>
      </visual>
    </link>
  </model>
</sdf>"""
    config_fname = mdir/'model.config'
    sdf_fname = mdir/'model.sdf'
    with open(config_fname, 'w') as f:
        f.write(config_string)
    with open(sdf_fname, 'w') as f:
        f.write(sdf_string)


    print(config_string)
    print(sdf_string)

def download_model(model_id, output_dir, get_thumb=True):
    base = "https://3dwarehouse.sketchup.com/warehouse/GetEntity"
    url = '?'.join([base,'id=' + model_id + '&showBinaryAttributes=true'])
    response = urllib2.urlopen(url).read().decode('utf8')
    data = json.loads(response)
    if 'zip' not in data['binaries']:
        return
    print(data['binaries']['zip']['url'])
    dwnld_url = data['binaries']['zip']['url']
    base, rest = dwnld_url.split('?', 1)
    params = dict([param.split('=') for param in rest.split('&')])
    model_id = params['subjectId']
    name = data['title']
    sub_output_dir = output_dir/model_id
    if not sub_output_dir.exists(): sub_output_dir.mkdir()
    fname = sub_output_dir/'model.zip'

    print(tc.colored('downloading '+fname, 'green'))
    data = urllib2.urlopen(dwnld_url).read()
    with open(fname, 'wb') as f:
        f.write(data)

    with zipfile.ZipFile(fname,"r") as zip_ref:
        zip_ref.extractall(sub_output_dir)
    dae_fname = sub_output_dir/'model.dae'
    #cmd = ['meshlabserver', '-i', dae_fname, '-o', dae_fname, '-om', 'vt', 'wt']
    #print(' '.join(cmd))
    #subprocess.call(cmd)

    generate_sdf(sub_output_dir,model_id)

    if get_thumb:
        thumb_fname = sub_output_dir/'thumb.jpg'
        download_thumb(model_id, thumb_fname)
    # upload/create json metadata
    json_fname = sub_output_dir/'metadata.json'
    print(tc.colored('saving metadata '+json_fname, 'green'))
    data = {'mid': model_id, 'name': name}
    util.json_dict_update(json_fname, data)

def download_query(query_url, existing_model_ids, output_dir):
    model_ids = get_model_ids(query_url)
    print(model_ids)
    for model_id in model_ids:
        if not model_id in existing_model_ids:
            download_model(model_id, output_dir)
        else:
            print(tc.colored('%s is dupe, skipping'%model_id, 'red'))
parser = argparse.ArgumentParser(description='scrape models from warehouse 3D')
parser.add_argument('collection_id', nargs=1, help='URL of collection or query')
parser.add_argument('--dest', '-d', help='Directory to save models')
parser.add_argument('--existing', '-e', help='json with existing model ids to avoid duplication.')

args = parser.parse_args()
collection_id = args.collection_id[0]
base =  "https://3dwarehouse.sketchup.com/warehouse/Search"
params = '&'.join(['parentCollectionId='+collection_id, 'class=entity', 'startRow=1','endRow=1000','%24I=true','li=false'])
collection_url = '?'.join([base, params])
print(tc.colored('Collection url:', 'green'), tc.colored(collection_url, 'white'))

if args.dest:
    output_dir = path.path(args.dest)
else:
    output_dir = path.path('./models')

print(tc.colored('output dir:', 'green'), tc.colored(output_dir, 'white'))
if not output_dir.exists(): output_dir.mkdir()

if not args.existing and output_dir/'existing.json':
    args.existing = output_dir/'existing.json'
else:
    args.existing = path.path(args.existing)

if args.existing.exists() :
    with open(args.existing) as f:
        existing_model_mids = set(json.load(f))

    print('%d existing models'%len(existing_model_mids))
else:
    existing_model_mids = set()   
download_query(collection_url, existing_model_mids, output_dir)
# update existing existing_model_mids
model_ids = set(map(str, [d.basename() for d in output_dir.dirs()]))
existing_model_mids = existing_model_mids.union(model_ids)
to_save = sorted(list(existing_model_mids))
print('updating %s'%args.existing)
with open(args.existing, 'w') as f:
    json.dump(to_save, f)
