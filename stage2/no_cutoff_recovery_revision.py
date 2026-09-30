"""Fixed execution-location amendment after an unstarted launch refusal.

The original plan and all three keys stay unchanged. The first installation
is retained, never patched or resumed. This stdlib-only reader authenticates
the actual old baseline manager invocation and the untouched unstarted tree.
It is not qualification, an archive audit or authority to repeat an attempt.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r6')
RETIRED = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260929')
REJECTED = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r2')
BASELINE = Path('/opt/uts-capstone-corrected-20260923')
COMMIT = 'c9b357c3a4dde44b04900ec8d6bc719981124a84'
SERVICE = 'uts-stage2-corrected-20260923.service'
REFUSED_UNIT = 'uts-recovery-qualify-c1a2783fc4f2d308300adb630415aedb.service'
BOOT = '3e30b45e3cf44d3f805689699574fb73'
INVOCATION = '399b6d0034d34aafb4858fe1e41d08c1'
EVENTS = (
    ('7d4958e842da4a758f6c1cdc7b36dcc5', '1790114328574818',
     '99c0e690a376976302c0afc7cc2935013a2fe86ced44fb50e40e6e6ce63bab0c'),
    ('39f53479d3a045ac8e11786248231fbf', '1790114328618033',
     '027228985581db2e263a279d6ae87aaf58f4197e757e27a0bfd0baaecf398136'),
    ('7ad2d189f7e94e70a38c781354912448', '1790298517125110',
     'c891aced25ccfa0c3bd7e7db74a4746dd8047ffb2bf1a7ca688848367eb3c63b'),
    ('ae8f7b866b0347b9af31fe1c80b127c0', '1790298517125572',
     '5b2a629234771a9a7d59a9b7a8a68e0cc80154508684410a9f5a4799de068755'))
RECORDS = {
    'installation-intent.json': 'fa47b9124983b7ead60c6b3f921cc3e748f5a6c259bdf35e9633c3acd1ec7160',
    'installation-files.json': 'f5b66b7bf45747d59f7556c2368f344c6d56a833a7f9aa9c93290db304e5f316',
    'installation-result.json': 'c4bafa52f4ef146b6b1cb6c54e9abb00aa31c89b77da4aa6822e651eb5ab9a69',
    'source-commit.txt': '2927c7aca7991b21428dc60549ab10fb3bd9402160bd2f509914ba17654a799b'}
SOURCE_MAP = '936adc773d85fddda9e1be464e269bdd6515e171b25d4cb7d9659863a8714a0a'
REJECTED_UNIT = 'uts-recovery-qualify-319ee77d63cd9852455863e4947088dc.service'
REJECTED_INVOCATION = 'e3d8f5dbacaf480ea7dda744932d7bdc'
REJECTED_RECORDS = {
    "installation-intent.json": "f38082ad0e3fba260cd71974162087ea948c6d4dd8d28de9214f3e832c74132f",
    "installation-files.json": "33129d47cc11a4fd2f595c00709354adc5ac7871be0b9e282e9775aa249458e9",
    "installation-result.json": "6600e0cd9eefdd49521a097853f3654b429066c3ff0637c62f8492d54332d9ac",
    "source-commit.txt": "736850f51721e5c65ee6d1ab4241ba354926df336361aa077f604e6b7daad7fb"
}
REJECTED_SOURCE_MAP = '8f2b7daecc7db1a6cdf68d2b4c23ffe6d277ce76b69667780974beae15ceb9a2'
REJECTED_FILES = {
    ".runtime/stage2/no-cutoff-recovery-credit-policy.json": "15460104bd6794a8b2af7d7761cc61a7a7541c79204abb715a9796d7908c8161",
    ".runtime/stage2/no-cutoff-recovery-image-build-failure.json": "70bc194867682398847de58d4df86f36c8f45a5cb8e6bd5ab037041de4c2dd81",
    ".runtime/stage2/no-cutoff-recovery-image-build.json": "9725b568e285c6b31752395456b15a7d13ffa587285da84d0089d0f42965ff4d",
    ".runtime/stage2/no-cutoff-recovery-plan.json": "0ea9ef5f27558c441bb10dc1f5278dde15f262877011930464f5c408c284220a",
    ".runtime/stage2/no-cutoff-recovery-predecessor.json": "6ff1c2275bb6cc4c58ce6218b4b6e01216a1734179925fc24a6e294dc4e10018",
    ".runtime/stage2/no-cutoff-recovery-qualification-failure.json": "8771172e9a6db451637aab7797e356cdd2abbb72be307f0ad8b64fe1fce5a0f8",
    ".runtime/stage2/no-cutoff-recovery-qualification-intent.json": "5d7ece34f9e4b6f3cc6b9e7728a1802306170f16f06d7d9fb2285efcdc85b10f",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/accepted.json": "7ee950d1f3fcf56a6e0c83ce29036c74c07b94efb975d4ecc40a51cf93570a7c",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/failure.json": "86041a594dff542d1621e6dcbd239a46268f375bab86b990777bcbcebc02ffa7",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/intent.json": "03e799b6a2f7709b3cf272d8145e55ba1b4410247791a9138e2c8f7ef3f4309a",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/prerequisites.json": "eac857a5298d620d0e8926e9bf03d3f2314cd964e98caf14aabd511fbf6d28ab",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/service-started.json": "11d54929de1d34410809aaa1f493066b6fecf8ab964eed87062d75e971c28c34",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/service.log": "0d91cc5e2c0a41f4baec37c983ae0b1dee5dea8d77b556f807e7eaf7abba2874",
    ".runtime/stage2/no-cutoff-recovery-runtime.json": "87f508cb0f15ffc7a63ee536f304a43a7019395b1fd1aa69338c766cb00e2aba"
}
REJECTED_DIRECTORIES = (
    '.runtime/stage2/native-no-cutoff-recovery-qualification-ac4181d246ca4db382b7bcb93bf42ac3',
    '.runtime/stage2/no-cutoff-recovery-image-docker-config',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection')
REJECTED_IMAGES = {
    "sha256:780a545c444b5b1d8f8afa7252f27e1201e1c62d840a043dd9f15bbc822aa23b": "f5acb7af91cbb80cc0ea4fdd2710be44a31b0f8bdd3971d93c7fd74796b3007e",
    "sha256:6211ce5a6c2845135104f36fd2940588a1b256224c9a89fc267f4967bb8054b0": "654173da9ed4c6419a24034ff1a2fc55b0b9bccce8419d42b328d7fd07bedc2a",
    "sha256:69a331f7aef9f7c33ede8371fc7109ef0d83fe4f946f05f2a4aad97e65a51cc4": "92cd6776f6f4f1f7187a4503f436d521d11beb65c703050e781ba61f6a08b086"
}
REGRESSION_REJECTED = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r3')
REGRESSION_UNIT = 'uts-recovery-qualify-7f1c3287f20e1ee133e07336ac901ee0.service'
REGRESSION_INVOCATION = 'e9ea53fbea8c470e816a4cb122d7ff54'
REGRESSION_RECORDS = {
    "installation-files.json": "dbda9115d11a0159e7400281f3e7e58d6a7df385c95c33046591773f66cdde1f",
    "installation-intent.json": "94449e62ecdffe5368c2b87a3b01a8a0aa4d8b03f25d896b8181277be65569d2",
    "installation-result.json": "bc5f8998bd80567513d7efdb8107f42aa40fe86db2588888f43114a95f9ecaba",
    "source-commit.txt": "9adc2f15272d55c64acf7145a8414711de2a1dc35b3c281ec2def12c9d8115c5"
}
REGRESSION_SOURCE_MAP = '94c4a4f83a3dae6b821c89b1a55cf550e799c73f2400877ba5d7570f094299dc'
REGRESSION_FILES = {
    ".runtime/stage2/native-no-cutoff-recovery-qualification-91369a09519f4f428aa19ec0bd6d1467/regression.txt": "e06fe0acb2c1e77c66e9250991844a7db1fcc003425ac607891284f43b84e821",
    ".runtime/stage2/no-cutoff-recovery-credit-policy.json": "15460104bd6794a8b2af7d7761cc61a7a7541c79204abb715a9796d7908c8161",
    ".runtime/stage2/no-cutoff-recovery-image-build.json": "23667fe601677c4e69afc30a37dd8afa491d29dc7bdf6f8257fbdc261a02ac83",
    ".runtime/stage2/no-cutoff-recovery-images.json": "03917f4f39438f10de4e9370711f3882a343216da6804ede710fa00b66172eae",
    ".runtime/stage2/no-cutoff-recovery-plan.json": "0ea9ef5f27558c441bb10dc1f5278dde15f262877011930464f5c408c284220a",
    ".runtime/stage2/no-cutoff-recovery-predecessor.json": "6ff1c2275bb6cc4c58ce6218b4b6e01216a1734179925fc24a6e294dc4e10018",
    ".runtime/stage2/no-cutoff-recovery-qualification-failure.json": "44cd8ec9708a1ab6549afe070cd38d1d63f1b4b3fb60632597dfd588d4cb7b07",
    ".runtime/stage2/no-cutoff-recovery-qualification-intent.json": "191f60a27e9a7540486f40468b6d3a74f4beea4a50cd598e4b63cb1fdaad5ecd",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/accepted.json": "f780dc4e2f1c33d2f1a9f18bb8c1b337fd5c4428d757dcb93acb475263378cf7",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/failure.json": "edd9ab2d315b9438776332897acebe6b6576360ad39228111257caadf11743a2",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/intent.json": "03089b917d207fd3da24e0faa42ddda3917a891c2ebe0d93ab9e2adcc4dd8d92",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/prerequisites.json": "4e2b335989ec7a43c68aae09026ec01aa4f9ab7e6b2bb1ad2c207a68d9d87864",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/service-started.json": "a257eda8346f64d14062cba3f376153daabb07dcd7682cc43057749b632c70ed",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection/service.log": "61a1958d533899d2f5c5b32e2cd99ba5c372d64355b77c0dd2fd715f6ca929fc",
    ".runtime/stage2/no-cutoff-recovery-runtime.json": "6450b6e5afd96a2b7f4637e3082e4b6406f99e128e388d0d9028013419e332b9",
    ".venv/lib/python3.12/site-packages/__pycache__/_virtualenv.cpython-312.pyc": "2e272e87f5fa35db8a72f9dd3b2e1d6622b4a06840b0efcdcf3f9bd20a969733"
}
REGRESSION_DIRECTORIES = tuple([
    ".runtime/stage2/native-no-cutoff-recovery-qualification-91369a09519f4f428aa19ec0bd6d1467",
    ".runtime/stage2/native-no-cutoff-recovery-qualification-91369a09519f4f428aa19ec0bd6d1467/test-tmp",
    ".runtime/stage2/no-cutoff-recovery-image-docker-config",
    ".runtime/stage2/no-cutoff-recovery-qualify-connection",
    ".venv/lib/python3.12/site-packages/__pycache__"
])
REGRESSION_IMAGES = {
    "sha256:69a331f7aef9f7c33ede8371fc7109ef0d83fe4f946f05f2a4aad97e65a51cc4": "92cd6776f6f4f1f7187a4503f436d521d11beb65c703050e781ba61f6a08b086",
    "sha256:780a545c444b5b1d8f8afa7252f27e1201e1c62d840a043dd9f15bbc822aa23b": "f5acb7af91cbb80cc0ea4fdd2710be44a31b0f8bdd3971d93c7fd74796b3007e",
    "sha256:d9650b626cae3e27cdf2b5bd95649cb4da8f8c0a6d11127cba65b9663be91eb7": "bd802a2587197b3823c7d239a556c0e3853458fc4e837dbeeb0b45c92a1cb7ef"
}
CONNECTION_REJECTED = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r4')
CONNECTION_UNIT = 'uts-recovery-qualify-43aef4a7066003697fe4e73f12f2f03b.service'
CONNECTION_INVOCATION = 'b9d16f8f41d24de7b88339979f0ee43b'
CONNECTION_RECORDS = {
    'installation-files.json': '7f5c356b6fa205cbb76a84a45a67df9d1b7bbb4b6ba995ebbb1729b093deb337',
    'installation-intent.json': '5eaa2d2769a6c1926588b56994a024ddc9eefd58c5051eaf421eaf57365836f2',
    'installation-result.json': 'a5fe787d75a2cab313890186a516d0fdc5b168cd74deb4fc3a78a778072ae90e',
    'source-commit.txt': '3befbe4cbaf93c3c67a64cf8b6440cfb0cb819522157f6c576d3dd1c8e00493c'}
CONNECTION_SOURCE_MAP = '34242e32cf1fb1b3cba96ddbfb2a8f6e75741c65817b2fce4c5c15894c253e75'
CONNECTION_FILES = {
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/failure.json': '18b4e2cd7bbdac03f8672e6946eea24e6b8031ce5164d711f28e2e7f991f542d',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/intent.json': '80de8c0b26878d7c95d3a08d2c5d4675048833fed79135876088e6d061b6027b',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/relay-failure.json': '18b4e2cd7bbdac03f8672e6946eea24e6b8031ce5164d711f28e2e7f991f542d',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/service-started.json': 'f60b0a9b657d0d972fd60fa54fe9b47576d7010e2b9ca27c1a999d402a432b43',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/service.log': '3f767f4ee721f508fb2c9f7d5be320b4a48cff70b6b5c332d42259fe09ca22c6'}
CONNECTION_DIRECTORIES = ('.runtime/stage2/no-cutoff-recovery-qualify-connection',)
SYMLINK_REJECTED = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r5')
SYMLINK_UNIT = 'uts-recovery-qualify-aa6e9b58cac893f63450d7fac8dbd0f9.service'
SYMLINK_INVOCATION = '590b186ef537475bb697bfd2489d5d14'
SYMLINK_RECORDS = {
    'installation-files.json': 'd5af09c5f59e779ac3e459ec7abc07ded7031ba7794eaf0714f0783cd52d1b01',
    'installation-intent.json': '5530b6d3789f339e6e91d3ae23b92f1dea2860543bf9fba2261f11d27b8b2cb7',
    'installation-result.json': '85ec9f9b172a280174c4879b4cb2ecd7a6b1b006deadfc886e0a1919c9977011',
    'source-commit.txt': 'cbdd404fce56d56724a75970d6cd340a16255082ae377a68996586b1747cee6d'}
SYMLINK_SOURCE_MAP = '681aaa459251d15f773fe891141ce91c7104d1f0c412dd92c361f3f12d238ec6'
SYMLINK_FILES = {
    '.runtime/stage2/native-no-cutoff-recovery-qualification-501d6d1bdb84402bb84b19183cdd52a3/regression.json': 'd8c91530dc3159890b4e842aaa962731c2ccf35f6ad0c1c5d161d595798894b3',
    '.runtime/stage2/native-no-cutoff-recovery-qualification-501d6d1bdb84402bb84b19183cdd52a3/regression.txt': '5a6cce9806c6fc968748f5e2dd1811ef63e5d62a385344efd98e38ab92607fa3',
    '.runtime/stage2/no-cutoff-recovery-credit-policy.json': '15460104bd6794a8b2af7d7761cc61a7a7541c79204abb715a9796d7908c8161',
    '.runtime/stage2/no-cutoff-recovery-image-build.json': '0d7c9ad2c22a68c9d6ca628f0b31845aa1c8a5dd8aea52f5f6f5df406225c452',
    '.runtime/stage2/no-cutoff-recovery-images.json': '4e0e7bdca9a638674e83c21e3d421edc44ce592750b39d9a6941e4c7eb7d50f3',
    '.runtime/stage2/no-cutoff-recovery-plan.json': '0ea9ef5f27558c441bb10dc1f5278dde15f262877011930464f5c408c284220a',
    '.runtime/stage2/no-cutoff-recovery-predecessor.json': '6ff1c2275bb6cc4c58ce6218b4b6e01216a1734179925fc24a6e294dc4e10018',
    '.runtime/stage2/no-cutoff-recovery-qualification-failure.json': 'e7331fa0d1f51c7443d86cec225d8da85f2f689633a5a9439c265ce697ee0905',
    '.runtime/stage2/no-cutoff-recovery-qualification-intent.json': '61ab3d0338dfd9db32ee2048e6287fe24cd63061e3051316429039e0e3a32f57',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/accepted.json': '93ae6cb97b6bf8b55642983771bcc7822fcb4dbf10ba2f0e4d3be4049ea10945',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/failure-diagnostic.json': '02c3ee80165672f354d01f0cb7199bf1fa679c9ec2632c535eb1cb4f994792be',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/failure.json': 'c1308804e6619c96788e6566c08e4b22decdddfed940c1c0dab7633e28ea27b9',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/intent.json': '43943f772e48f0e18c4bb80d6a57d85f6b9a824afd017d93fde0b10114132e16',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/prerequisites.json': 'b716f6c2f1b0697aedebd9a51da87589e248d31cb6b304da4a38e5ba420aa5ea',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/service-started.json': 'd48589fcd8dd5125f4e185438084c59d2398d02882f0b0dfc3c0df2767d5f13c',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection/service.log': '3e631b2a321f833d6542ec97eb40f864e6fdefb2bcc916dc7df206962013ef8a',
    '.runtime/stage2/no-cutoff-recovery-runtime.json': '5dbc02749f3981ce8e818d03dce6ac0266b2fd0533e0c46dff923867557133cb',
    '.venv/lib/python3.12/site-packages/__pycache__/_virtualenv.cpython-312.pyc': '3f68b14148270d67768a841218471dca39c8e8135cafd052b1e5792682a0a9ee'}
SYMLINK_DIRECTORIES = (
    '.runtime/stage2/native-no-cutoff-recovery-qualification-501d6d1bdb84402bb84b19183cdd52a3',
    '.runtime/stage2/native-no-cutoff-recovery-qualification-501d6d1bdb84402bb84b19183cdd52a3/test-tmp',
    '.runtime/stage2/no-cutoff-recovery-image-docker-config',
    '.runtime/stage2/no-cutoff-recovery-qualify-connection',
    '.venv/lib/python3.12/site-packages/__pycache__')
SYMLINK_IMAGES = {
    'sha256:69a331f7aef9f7c33ede8371fc7109ef0d83fe4f946f05f2a4aad97e65a51cc4': '92cd6776f6f4f1f7187a4503f436d521d11beb65c703050e781ba61f6a08b086',
    'sha256:780a545c444b5b1d8f8afa7252f27e1201e1c62d840a043dd9f15bbc822aa23b': 'f5acb7af91cbb80cc0ea4fdd2710be44a31b0f8bdd3971d93c7fd74796b3007e',
    'sha256:c5f20262cd394e6328b35b83820e77a31d7fc8cefacf57b88af93c2fd1615bfb': '70ff3fef82029087770528557c4ab1fe4eee8328711fbb7bf2b341a55c3d2815'}
OPERATOR_STATES = {
    '.runtime/netcup/custom-no-cutoff-recovery-installation-20260930-r6': {
        'intent.json': '129120fa24218c5234d0eecf9d4928033947cf95cbd5a29081c2be0d7d1ae83d',
        'result.json': SYMLINK_RECORDS['installation-result.json']},
    '.runtime/netcup/custom-no-cutoff-recovery-qualify-20260930-r5': {
        'failure.json': '5f1db1fce33cfda0a56f4a1f600455ee5c87700a546d3e115f7d330f28d7ccfe',
        'intent.json': '3994909f59d1bd0e619e273d4e003e988195c4e162e0f111b7c6d6898ed60a81',
        'receiver.json': '94f43b759ff1120131a6e054b5f0a1c052769208cd9c09cd30265879a4fcad9a'},
    '.runtime/netcup/custom-no-cutoff-recovery-installation-20260930-r5': {
        'intent.json': '85fd2e7e14484848ba493392f0acb13c57a0fea69a73ec31ae50b89be20a5d16',
        'result.json': CONNECTION_RECORDS['installation-result.json']},
    '.runtime/netcup/custom-no-cutoff-recovery-qualify-20260930-r4': {
        'intent.json': 'c22198085ebde8c0fd2ad2d7bbce41ca3d70d2b0eae0d8b0b09b5ea0fb18eb52',
        'receiver.json': '570966939f25d55b95096ab9fc85aa6a7102665005760822583ecbad0ac01f02',
        'failure.json': '4afef265e1cf768dd6551f247c855ab6c401b2ebec4e4be11394cd6e914072d7'},
    '.runtime/netcup/custom-no-cutoff-recovery-installation-20260930-r4': {
        'intent.json': '6204671db54e7ec44bbf47ac577c8b9376f88d3fd729abd6e6aa259b70944b69',
        'result.json': REGRESSION_RECORDS['installation-result.json']},
    '.runtime/netcup/custom-no-cutoff-recovery-qualify-20260930-r3': {
        'intent.json': '8259644c2e7a65de6b2c5bb429242be3a02d303a7f51aa393d07cf661c55e211',
        'receiver.json': '3684b9685d36b7f08150ab2c8da9f027fa8114d1f1dbc8023dabd3a65644a1c0',
        'failure.json': 'fe3a1310d7dfa22319b9e365b5e434ed41bccc895597b59521d16f51829044e8'},
    '.runtime/netcup/custom-no-cutoff-recovery-installation-20260930-r3': {
        'intent.json': '075a03a25d33f5d1b0e8c1546a6dd2f3c988d8c1999638ca0ffaad78ea7c5625',
        'result.json': REJECTED_RECORDS['installation-result.json']},
    '.runtime/netcup/custom-no-cutoff-recovery-qualify-20260930-r2': {
        'intent.json': '3fd944337a09c01cb2fba5273ff3f96bf068440c00e7984897dc0db452ec49ed',
        'receiver.json': '46e31a8130d18f5e426a230f4e11facece29e1b8f03a6aeeeb54db6e38fd3dc0',
        'failure.json': '06c8ad879d483040e269a121c040dc1d0e65881787126fc87d577983bdec32f5'},
    '.runtime/netcup/custom-no-cutoff-recovery-installation-20260930-r2': {
        'intent.json': '466c4814d29b689b0139462e34537f2cc89e6f920c927f6c6cbb8f9587740b8f',
        'result.json': RECORDS['installation-result.json']},
    '.runtime/netcup/custom-no-cutoff-recovery-qualify-20260929': {
        'intent.json': '3de257fd2a19a1ed27f0a18488b31d697161be6974cfe48fc716e97a047cc768',
        'failure.json': '80c50f1549f0625058c82b2a136822a5b63e4783b0134ecb37dbeb8da227fca4'}}
OWNER = GROUP = 0
PROC = Path('/proc')
CGROUP = Path('/sys/fs/cgroup/system.slice')
WINDOW = 64 * 1024 * 1024  # Metadata framing only, not a task limit.
ENV = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}


def _fail():
    raise ValueError('Actual baseline completion and unchanged unstarted installation required')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value: _fail()
        value[key] = item
    return value


def _loads(raw):
    def nonfinite(_): _fail()
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=nonfinite)
    if type(value) is not dict: _fail()
    return value


def _relative(name):
    if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_!.\-/]+', name)
            or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))):
        _fail()
    return name


def _acl(path):
    if not hasattr(os, 'listxattr') or any(n in {'system.posix_acl_access', 'system.posix_acl_default'}
            for n in os.listxattr(path, follow_symlinks=False)):
        _fail()


def _directories(path, private=False):
    answer = []
    for p in (*reversed(path.parents), path):
        s = p.lstat(); _acl(p)
        if (p.resolve() != p or not stat.S_ISDIR(s.st_mode) or s.st_uid not in {0, OWNER}
                or s.st_gid not in {0, GROUP} or s.st_mode & 0o7022
                or p == path and private and stat.S_IMODE(s.st_mode) != 0o700):
            _fail()
        answer.append((str(p), s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid))
    return tuple(answer)


def _read_at(base, name, expected):
    p = base / _relative(name); parents = _directories(p.parent)
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno()); _acl(p)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != OWNER
                or before.st_gid != GROUP or before.st_mode & 0o7022
                or (name.startswith('.runtime/') or name in RECORDS) and stat.S_IMODE(before.st_mode) != 0o600
                or before.st_size > WINDOW):
            _fail()
        raw = stream.read(WINDOW + 1); after = os.fstat(stream.fileno())
    if (len(raw) > WINDOW or _sha(raw) != expected or _identity(before) != _identity(after)
            or _identity(after) != _identity(p.lstat()) or _directories(p.parent) != parents):
        _fail()
    return raw, _identity(after)


def _read(name, expected):
    return _read_at(RETIRED, name, expected)


def _command(args):
    try: value = subprocess.run(args, capture_output=True, text=True, timeout=30, env=dict(ENV))
    except (OSError, subprocess.SubprocessError): _fail()
    if value.returncode or len(value.stdout.encode('utf-8')) > WINDOW: _fail()
    return value.stdout


def _state(unit):
    raw = _command(['systemctl', 'show', unit,
        '--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus'])
    if any('=' not in line for line in raw.splitlines()): _fail()
    state = _pairs(line.split('=', 1) for line in raw.splitlines())
    if (state.get('LoadState') not in ('loaded', 'not-found') or state != dict(
            LoadState=state.get('LoadState'), ActiveState='inactive', SubState='dead',
            MainPID='0', ExecMainStatus='0')):
        _fail()
    if unit == REFUSED_UNIT and state['LoadState'] != 'not-found': _fail()
    return state


def _journal():
    fields = '__REALTIME_TIMESTAMP,_PID,_UID,_COMM,_BOOT_ID,SYSLOG_IDENTIFIER,UNIT,INVOCATION_ID,MESSAGE_ID,JOB_TYPE,JOB_RESULT,MESSAGE'
    raw = _command(['journalctl', '--no-pager', '--output=json', '--output-fields=' + fields,
        '_PID=1', '_UID=0', '_COMM=systemd', 'SYSLOG_IDENTIFIER=systemd', 'UNIT=' + SERVICE])
    rows = [_loads(line) for line in raw.splitlines()]
    if len(rows) != len(EVENTS): _fail()
    for row, (event, when, digest) in zip(rows, EVENTS):
        expected = dict(_PID='1', _UID='0', _COMM='systemd', _BOOT_ID=BOOT,
            SYSLOG_IDENTIFIER='systemd', UNIT=SERVICE, INVOCATION_ID=INVOCATION,
            MESSAGE_ID=event, __REALTIME_TIMESTAMP=when)
        if (any(row.get(k) != v for k, v in expected.items())
                or type(row.get('MESSAGE')) is not str or _sha(row['MESSAGE'].encode()) != digest):
            _fail()
    if (rows[0].get('JOB_TYPE') != 'start' or rows[1].get('JOB_TYPE') != 'start'
            or rows[1].get('JOB_RESULT') != 'done'
            or rows[2]['MESSAGE'] != SERVICE + ': Deactivated successfully.'):
        _fail()


def _processes():
    for unit in (SERVICE, REFUSED_UNIT):
        if (CGROUP / unit).exists() or (CGROUP / unit).is_symlink(): _fail()
    for path in PROC.iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid(): continue
        try:
            groups = (path / 'cgroup').read_text()
            if not groups.splitlines() or any(not re.fullmatch(r'[0-9]+:[^:\n]*:/[^\n]*', n) for n in groups.splitlines()): _fail()
            parts = [part for line in groups.splitlines() for part in line.split(':')[-1].split('/')]
            if any(unit in parts for unit in (SERVICE, REFUSED_UNIT)): _fail()
            for key in ('cwd', 'exe'):
                try: target = os.readlink(path / key).removesuffix(' (deleted)')
                except FileNotFoundError: continue
                if any(target == str(root) or target.startswith(str(root) + '/') for root in (BASELINE, RETIRED)): _fail()
        except FileNotFoundError: continue  # Process exited during observation.
        except OSError: _fail()
    for unit in (SERVICE, REFUSED_UNIT):
        if (CGROUP / unit).exists() or (CGROUP / unit).is_symlink(): _fail()


def baseline():
    """Fresh trusted manager/procfs observation; not-found defaults never suffice."""
    if sys.platform != 'linux' or os.getuid() != OWNER or os.getgid() != GROUP: _fail()
    before = _directories(BASELINE / '.runtime/stage2', True)
    if ((PROC / '1/comm').read_text().strip() != 'systemd'
            or (PROC / 'sys/kernel/random/boot_id').read_text().strip().replace('-', '') != BOOT):
        _fail()
    states = {unit: _state(unit) for unit in (SERVICE, REFUSED_UNIT)}
    _journal(); _processes()
    for name in ('operator-stop-request.json', 'provider-stop.json'):
        p = BASELINE / '.runtime/stage2' / name
        if p.exists() or p.is_symlink(): _fail()
    if (_directories(BASELINE / '.runtime/stage2', True) != before
            or {unit: _state(unit) for unit in states} != states):
        _fail()
    return states


def _retained_tree(base, record_hashes, source_count, source_hash, extra_files, extra_directories):
    """Reread original installed sources and exact unused tree, without credentials.

    Retired runtime payloads are inventoried/identity-checked, not read: they
    supply no current library or paid admission proof. The new root has its own
    full actual library comparison. No old archive or credential is opened.
    """
    root = _directories(base, True)
    _directories(base / '.runtime/stage2', True)
    records = {n: _read_at(base, n, h) for n, h in record_hashes.items()}
    inventory = _loads(records['installation-files.json'][0])
    if set(inventory) != {'files', 'runtime'} or type(inventory['files']) is not dict: _fail()
    sources = inventory['files']
    if len(sources) != source_count or _sha(json.dumps(sources, sort_keys=True, allow_nan=False).encode()) != source_hash: _fail()
    if set(sources) & set(extra_files): _fail()
    identities = {n: _read_at(base, n, h)[1] for n, h in {**sources, **extra_files}.items()}
    expected = set(sources) | set(record_hashes) | set(extra_files) | {'.runtime/stage2/' + n for n in ('matrix.lock', 'scored.lock', 'gateway.lock')}
    links = {}; directories = {''} | set(extra_directories)
    if type(inventory['runtime']) is not list: _fail()
    for tree in inventory['runtime']:
        if type(tree) is not dict or set(tree) != {'files', 'links', 'directories'}: _fail()
        for name in tree['files']: expected.add(_relative(name))
        for name, target in tree['links'].items():
            name = _relative(name)
            if name in links or type(target) is not str: _fail()
            links[name] = target; expected.add(name)
        directories.update(_relative(n) for n in tree['directories'])
    for name in expected:
        directories.update(p.as_posix() for p in Path(name).parents if p.as_posix() != '.')
    actual = {}; actual_directories = {}
    for current, children, names in os.walk(base, followlinks=False):
        current = Path(current); relative = current.relative_to(base).as_posix()
        actual_directories['' if relative == '.' else relative] = _directories(current)
        for name in list(children) + names:
            p = current / name; key = p.relative_to(base).as_posix(); s = p.lstat(); _acl(p)
            if stat.S_ISDIR(s.st_mode): continue
            if key in links:
                if (not stat.S_ISLNK(s.st_mode) or os.readlink(p) != links[key]
                        or s.st_uid != OWNER or s.st_gid != GROUP or s.st_nlink != 1): _fail()
            elif (not stat.S_ISREG(s.st_mode) or s.st_uid != OWNER or s.st_gid != GROUP
                    or s.st_nlink != 1 or s.st_mode & 0o7022): _fail()
            if key == '.env' or key.startswith('.runtime/'):
                if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode) != 0o600: _fail()
            actual[key] = _identity(s)
        children[:] = [n for n in children if not (current / n).is_symlink()]
    if set(actual) != expected or set(actual_directories) != directories: _fail()
    for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
        raw, identity = _read_at(base, '.runtime/stage2/' + name, _sha(b''))
        if raw or actual['.runtime/stage2/' + name] != identity: _fail()
    if any(actual[n] != identity for n, identity in identities.items()): _fail()
    for name, record in records.items():
        if _read_at(base, name, record_hashes[name]) != record: _fail()
    for name, identity in actual.items():
        if _identity((base / name).lstat()) != identity: _fail()
    for name, identity in actual_directories.items():
        if _directories(base / name) != identity: _fail()
    if _directories(base, True) != root: _fail()
    return dict(files=actual, directories=actual_directories)


def retained():
    return _retained_tree(RETIRED, RECORDS, 321, SOURCE_MAP, {}, ())

def _rejected_manager(base=None, unit=None, invocation=None, pid='1226555'):
    base = REJECTED if base is None else base
    unit = REJECTED_UNIT if unit is None else unit
    invocation = REJECTED_INVOCATION if invocation is None else invocation
    names = ('LoadState', 'ActiveState', 'SubState', 'MainPID', 'InvocationID',
        'Result', 'ExecMainCode', 'ExecMainStatus', 'ExecMainPID', 'NRestarts',
        'Restart', 'Type', 'RemainAfterExit', 'WorkingDirectory')
    raw = _command(['systemctl', 'show', unit, '--property=' + ','.join(names)])
    if any('=' not in line for line in raw.splitlines()): _fail()
    value = _pairs(line.split('=', 1) for line in raw.splitlines())
    expected = dict(LoadState='loaded', ActiveState='failed', SubState='failed', MainPID='0',
        InvocationID=invocation, Result='exit-code', ExecMainCode='1',
        ExecMainStatus='1', ExecMainPID=pid, NRestarts='0', Restart='no',
        Type='exec', RemainAfterExit='yes', WorkingDirectory=str(base))
    if value != expected: _fail()
    return value


def _rejected_processes(base=None, unit=None):
    """Read procfs only; no signal, wait loop, cleanup or resumed service."""
    base = REJECTED if base is None else base
    unit = REJECTED_UNIT if unit is None else unit
    for path in PROC.iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid(): continue
        try:
            groups = (path / 'cgroup').read_text()
            if not groups.splitlines() or any(not re.fullmatch(r'[0-9]+:[^:\n]*:/[^\n]*', n) for n in groups.splitlines()): _fail()
            if any(unit in line.split(':')[-1].split('/') for line in groups.splitlines()): _fail()
            for key in ('cwd', 'exe'):
                try: target = os.readlink(path / key).removesuffix(' (deleted)')
                except FileNotFoundError: continue
                if target == str(base) or target.startswith(str(base) + '/'): _fail()
        except FileNotFoundError: continue
        except OSError: _fail()


def _rejected_images(base=None, images=None):
    base = REJECTED if base is None else base
    images = REJECTED_IMAGES if images is None else images
    config = base / '.runtime/stage2/no-cutoff-recovery-image-docker-config'
    identity = _directories(config, True)
    if any(config.iterdir()): _fail()
    for reference, expected in images.items():
        raw = _command(['/usr/bin/docker', '--config', str(config),
            '--host=unix:///var/run/docker.sock', 'image', 'inspect', reference])
        values = json.loads(raw, object_pairs_hook=_pairs)
        if type(values) is not list or len(values) != 1: _fail()
        value = values[0]
        if (type(value) is not dict or value.get('Id') != reference
                or value.get('Os') != 'linux' or value.get('Architecture') != 'amd64'): _fail()
        selected = {k: value[k] for k in ('Id', 'Os', 'Architecture', 'RootFS', 'Config')}
        if _sha(json.dumps(selected, sort_keys=True, allow_nan=False).encode()) != expected: _fail()
    if _directories(config, True) != identity or any(config.iterdir()): _fail()
    return dict(images)


def rejected():
    """Preserve the actual failed qualifier and image; never grant admission."""
    before = _rejected_manager()
    _rejected_processes()
    images = _rejected_images()
    _rejected_processes()
    if _rejected_manager() != before: _fail()
    # Actual source, failure records, inventory and identities are read AFTER
    # the last manager/process/image observation. Runtime payloads, including
    # the credential, remain identity-only just as in the first retired tree.
    tree = _retained_tree(REJECTED, REJECTED_RECORDS, 324, REJECTED_SOURCE_MAP,
        REJECTED_FILES, REJECTED_DIRECTORIES)
    return dict(manager=before, images=images, retained_identity=tree,
        paid_attempts_started=0, qualification_passed=False)


def regression_rejected():
    """Read the fixed failed Linux regression tree; never rerun or repair it."""
    args = (REGRESSION_REJECTED, REGRESSION_UNIT, REGRESSION_INVOCATION, '1247160')
    before = _rejected_manager(*args)
    _rejected_processes(*args[:2])
    images = _rejected_images(REGRESSION_REJECTED, REGRESSION_IMAGES)
    _rejected_processes(*args[:2])
    if _rejected_manager(*args) != before: _fail()
    tree = _retained_tree(REGRESSION_REJECTED, REGRESSION_RECORDS, 325,
        REGRESSION_SOURCE_MAP, REGRESSION_FILES, REGRESSION_DIRECTORIES)
    return dict(manager=before, images=images, retained_identity=tree,
        paid_attempts_started=0, qualification_passed=False)


def connection_rejected():
    """Retain the failed pre-handoff r4 operation without restarting it."""
    args = (CONNECTION_REJECTED, CONNECTION_UNIT, CONNECTION_INVOCATION, '1271584')
    before = _rejected_manager(*args)
    _rejected_processes(*args[:2])
    if _rejected_manager(*args) != before: _fail()
    tree = _retained_tree(CONNECTION_REJECTED, CONNECTION_RECORDS, 326,
        CONNECTION_SOURCE_MAP, CONNECTION_FILES, CONNECTION_DIRECTORIES)
    return dict(manager=before, retained_identity=tree, paid_attempts_started=0,
        qualification_passed=False, handoff_accepted=False)


def symlink_rejected():
    """Preserve r5's actual failed tests, accepted handoff and installed images."""
    args = (SYMLINK_REJECTED, SYMLINK_UNIT, SYMLINK_INVOCATION, '1283430')
    before = _rejected_manager(*args)
    _rejected_processes(*args[:2])
    images = _rejected_images(SYMLINK_REJECTED, SYMLINK_IMAGES)
    _rejected_processes(*args[:2])
    if _rejected_manager(*args) != before: _fail()
    tree = _retained_tree(SYMLINK_REJECTED, SYMLINK_RECORDS, 327,
        SYMLINK_SOURCE_MAP, SYMLINK_FILES, SYMLINK_DIRECTORIES)
    return dict(manager=before, images=images, retained_identity=tree,
        paid_attempts_started=0, qualification_passed=False, handoff_accepted=True)


def inspect():
    before = baseline()
    first = retained()
    failed = rejected()
    regressions = regression_rejected()
    connection = connection_rejected()
    symlink = symlink_rejected()
    if (baseline() != before or retained() != first or rejected() != failed
            or regression_rejected() != regressions or connection_rejected() != connection
            or symlink_rejected() != symlink): _fail()
    return dict(kind='recovery_execution_location_amendment_not_admission',
        execution_root=str(ROOT), retained_unstarted_root=str(RETIRED),
        original_plan_unchanged=True, retained_installation_attempts_started=0,
        retained_identity=first, retained_failed_qualification=failed,
        retained_failed_regressions=regressions, retained_failed_connection=connection,
        retained_failed_symlink_tests=symlink, paid_launch_ready=False)
