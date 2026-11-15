# Map coverage

PhantomCare maps 467 of 468 analysis rows. The final address review preserved all 444 existing locations. The remaining row stays searchable.

| Outcome | Final count | Added in the 24-address review |
|---|---:|---:|
| Verified address point | 344 | 13 |
| Approximate street position or parcel point | 123 | 10 |
| Unmapped | 1 | 0 |

Two reviewed rows are alternate spellings or mailing-city labels of an existing mapped address. Both retain their original analysis keys and share the corresponding CAMS feature. Neither review scores nor registration groupings were changed.

For every case below, the original address fields were recovered from the [CMS Hospice Enrollments API](https://data.cms.gov/data-api/v1/dataset/25704213-e833-4b8b-9dbc-58dd17149209/data) and re-normalized to confirm the match to the analysis row. The review checked Census, CAMS, and, where applicable, assessor situs, local GIS, permits, historical CMS publications, and targeted OpenStreetMap records. Candidate comparisons used a 100-meter radius wherever a suitable anchor existed. The reviewed cache retains source records, URLs, precision and coordinates. Approximate markers distinguish Census interpolation from a point within a confirmed parcel. A street estimate has no guaranteed error radius.

## Results for the 24 previously unresolved addresses

### 1 N INDIAN HILL BLVD CLAREMONT CA 91711

Original CMS address: 1 N INDIAN HILL BLVD, STE 205, CLAREMONT, CA, 917114769

**Verified.** Assessor parcel 8313009006 confirms the N direction and the identical ZIP+4. CAMS omits N. Census returned no match. Accepted location: 1 N INDIAN HILL BLVD, CLAREMONT, CA 91711 (Los Angeles County). [Evidence 1](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D2091563&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 2](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%278313009006%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 1050 A COMMERCE CENTER DR LANCASTER CA 93534

Original CMS address: 1050 A COMMERCE CENTER DRIVE, LANCASTER, CA, 935345860

**Approximate.** Census and the Assessor agree on 1050 Commerce Center Drive. The CAMS parcel point is about 73 m away. The extra A is unconfirmed and no separate A point was found. Accepted location: 1050 COMMERCE CENTER DR, LANCASTER, CA, 93534 (Los Angeles County). [Evidence 1](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D2078534&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=1050+COMMERCE+CENTER+DR%2C+LANCASTER%2C+CA%2C+93534&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 1061W AVE M14 D PALMDALE CA 93551

Original CMS address: 1061W AVENUE M14 D, PALMDALE, CA, 935511430

**Approximate.** Census and HCAI confirm the hyphenated street and spaced W. The Assessor parcel matches the exact ZIP+4 and lies within 100 m of the Census anchor. The trailing D has no confirmed unit location. Accepted location: 1061 W AVENUE M-14, PALMDALE, CA 93551 (Los Angeles County). [Evidence 1](https://hcai.ca.gov/facility/alden-home-health-inc/) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=1061+W+AVE+M-14%2C+PALMDALE%2C+CA%2C+93551&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%273111022036%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 1112 1 2 N PACIFIC AVE GLENDALE CA 91202

Original CMS address: 1112 1/2 N PACIFIC AVE, GLENDALE, CA, 912022316

**Approximate.** The source contains a literal fraction that normalization split. Glendale and Census both return street-level results for 1112 1/2. The 1112 primary CAMS point and city point cannot establish the fraction. Accepted location: 1112 1/2 N PACIFIC AVE, GLENDALE, CA, 91202 (Los Angeles County). [Evidence 1](https://gismap.glendaleca.gov/arcgis/rest/services/Common/CAD_SiteAddress_Street/GeocodeServer) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D2260034&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=1112+1%2F2+N+PACIFIC+AVE%2C+GLENDALE%2C+CA%2C+91202&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 12241 FIRESTONE BLVD AB NORWALK CA 90650

Original CMS address: 12241 FIRESTONE BLVD AB, NORWALK, CA, 906509342

**Approximate.** The assessor and CAMS confirm the base street address near the Census anchor. The AB suffix and differing ZIP+4 are unconfirmed. Accepted location: 12241 FIRESTONE BLVD, NORWALK, CA, 90650 (Los Angeles County). [Evidence 1](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D2654912&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=12241+FIRESTONE+BLVD%2C+NORWALK%2C+CA%2C+90650&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 140N VICTORY BLVD BURBANK CA 91502

Original CMS address: 140N VICTORY BLVD, 105, BURBANK, CA, 915021848

**Verified.** The assessor confirms 140 N Victory and the exact CMS ZIP+4. The Census alternate on S Victory has no matching CAMS situs record and is outside the accepted 100 m check. Accepted location: 140 N VICTORY BLVD, BURBANK, CA 91502 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=140+N+VICTORY+BLVD%2C+BURBANK%2C+CA%2C+91502&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1107847&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272451014031%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 15050 IMPERIAL HWY LA MIRADA CA 90638

Original CMS address: 15050 IMPERIAL HWY, LA MIRADA, CA, 906381301

**Approximate.** HCAI and historical CMS surveys confirm the 15050 Imperial Highway site. Census adds E. CAMS and the targeted assessor search produced no matching primary point. Accepted location: 15050 E IMPERIAL HWY, LA MIRADA, CA, 90638 (Los Angeles County). [Evidence 1](https://hcai.ca.gov/facility/presbyterian-intercommunity-hospital-home-health-services-parent/) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=15050+E+IMPERIAL+HWY%2C+LA+MIRADA%2C+CA%2C+90638&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 151N SAN VICENTE BLVD 209 BEVERLY HILLS CA 90211

Original CMS address: 151N SAN VICENTE BLVD 209, BEVERLY HILLS, CA, 902112323

**Verified.** The assessor ZIP+4 and Beverly Hills parcel inventory both identify parcel 4334022041 as 151 N. CAMS labels that same parcel S. Historical CMS confirms suite 209. The Census anchor is approximately 33 m away. Accepted location: 151 N SAN VICENTE BLVD, BEVERLY HILLS, CA 90211 (Los Angeles County). [Evidence 1](https://beverlyhills.granicus.com/MetaViewer.php?clip_id=8132&meta_id=489960&view_id=49) [Evidence 2](https://www.cms.gov/files/document/r12405otn.pdf) [Evidence 3](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=151N+SAN+VICENTE+BLVD%2C+BEVERLY+HILLS%2C+CA%2C+90211&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 4](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D2417408&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 5](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%274334022041%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 15455 SAN FERNANDO BLVD MISSION HILLS CA 91345

Original CMS address: 15455 SAN FERNANDO BLVD, SUITE 103A, MISSION HILLS, CA, 913451342

**Verified.** The assessor situs and Census identify San Fernando Mission Boulevard. CAMS links the point to the same parcel despite a San Fernando mailing-place label. The original road name omits Mission. Accepted location: 15455 SAN FERNANDO MISSION BLVD, MISSION HILLS, CA 91345 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=15455+SAN+FERNANDO+MISSION+BLVD%2C+MISSION+HILLS%2C+CA%2C+91345&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1606221&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272664007024%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 16501 SHERMAN WAY VAN NUYS CA 91406

Original CMS address: 16501 SHERMAN WAY, STE 105A, VAN NUYS, CA, 914063757

**Verified.** CAMS and Census agree on the missing W. The distinct civic point is roughly 22 m from the Census anchor. The suite is not a separate map point. Accepted location: 16501 W SHERMAN WAY, VAN NUYS, CA 91406 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=16501+W+SHERMAN+WAY%2C+VAN+NUYS%2C+CA%2C+91406&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1981360&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272226001906%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 16555 SHERMAN WAY VAN NUYS CA 91406

Original CMS address: 16555 SHERMAN WAY, STE B2, VAN NUYS, CA, 914063781

**Verified.** CAMS and Census agree on the missing W. The distinct civic point is about 31 m from the Census anchor. It shares an assessor parcel with 16501 but has a separate address point. Accepted location: 16555 W SHERMAN WAY, VAN NUYS, CA 91406 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=16555+W+SHERMAN+WAY%2C+VAN+NUYS%2C+CA%2C+91406&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1553953&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272226001906%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 18711 SHERMAN WAY RESEDA CA 91335

Original CMS address: 18711 SHERMAN WAY, SUITE 101B, RESEDA, CA, 913354000

**Approximate.** Census adds W. CAMS records a unit range and the assessor confirms the civic address. The unit range does not identify suite 101B. Accepted location: 18711 W SHERMAN WAY, RESEDA, CA, 91335 (Los Angeles County). [Evidence 1](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1291164&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=18711+W+SHERMAN+WAY%2C+RESEDA%2C+CA%2C+91335&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 19725 SHERMAN WAY CANOGA PARK CA 91306

Original CMS address: 19725 SHERMAN WAY, STE 220, CANOGA PARK, CA, 913063668

**Verified.** Census and CAMS agree on the civic site within 30 m. Census includes W and uses Canoga Park. CAMS uses Winnetka. The assessor confirms house, street and ZIP5. The existing analysis row has the same corrected house number, street, ZIP and CAMS feature ID. Both registration keys refer to the same mapped address. Accepted location: 19725 SHERMAN WAY, CANOGA PARK, CA 91306 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=19725+W+SHERMAN+WAY%2C+CANOGA+PARK%2C+CA%2C+91306&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1560984&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272115019023%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 2605 1 2 W BEVERLY BLVD MONTEBELLO CA 90640

Original CMS address: 2605 1/2 W BEVERLY BLVD, MONTEBELLO, CA, 906402309

**Approximate.** Census accepts the fraction restored from the original CMS line, but returns the same interpolation for 2605. CAMS returned no compatible point for either. Accepted location: 2605 1/2 W BEVERLY BLVD, MONTEBELLO, CA, 90640 (Los Angeles County). [Evidence 1](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=2605+1%2F2+W+BEVERLY+BLVD%2C+MONTEBELLO%2C+CA%2C+90640&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 2955E HILLCREST DR 128 WESTLAKE VILLAGE CA 91362

Original CMS address: 2955E HILLCREST DR 128, WESTLAKE VILLAGE, CA, 913623178

**Approximate.** Historical CMS identifies suite 128 in Thousand Oaks. Census confirms Ventura County and the same point under both city labels. OSM shows the corresponding addressed building about 3 m away. The pin preserves the Census coordinate and its street precision. Accepted location: 2955 E HILLCREST DR, THOUSAND OAKS, CA, 91362 (Ventura County). [Evidence 1](https://www.cms.gov/files/document/r11776otn.pdf) [Evidence 2](https://www.openstreetmap.org/way/723774294) [Evidence 3](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=2955+E+HILLCREST+DR%2C+THOUSAND+OAKS%2C+CA%2C+91362&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 3939 ATLANTIC AVE 216 LONG BEACH CA 90807

Original CMS address: 3939 ATLANTIC AVE 216, LONG BEACH, CA, 908073535

**Verified.** Long Beach's exact primary address point and assessor parcel 7139003047 corroborate the civic address. CAMS contains unit points with an S prefix, but the municipal point identifies the building and does not locate suite 216. Accepted location: 3939 ATLANTIC AVE, LONG BEACH, CA, 90807 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=3939+ATLANTIC+AVE%2C+LONG+BEACH%2C+CA%2C+90807&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://gis.longbeach.gov/fed/rest/services/Locators/CLB_AddressPoints_WGS/GeocodeServer/findAddressCandidates?SingleLine=3939+ATLANTIC+AVE%2C+LONG+BEACH%2C+CA%2C+90807&outFields=Addr_type%2CMatch_addr%2CAddNum%2CPostal&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%277139003047%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 444 E HUNTINGTON DR ARCADIA CA 91006

Original CMS address: 444 E HUNTINGTON DR, STE 103, ARCADIA, CA, 910066257

**Approximate.** Historical CMS and current city permits corroborate the address. City's permit ties it to assessor parcel 5773015026. The housing inventory APN is inconsistent with current situs. West Huntington and the same-number Monrovia point were rejected. OSM confirms the east-side address but gives a different ZIP. Accepted location: 444 E HUNTINGTON DR, ARCADIA, CA 91006 (Los Angeles County). [Evidence 1](https://www.arcadiaca.gov/Document%20Center/Government/Development%20Services/Building%20Services/Permit%20Activity%20Report/2026/March%202026%20Permit%20Summary.pdf) [Evidence 2](https://www.cms.gov/files/document/r12405otn.pdf) [Evidence 3](https://www.openstreetmap.org/way/406232662) [Evidence 4](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%275773015026%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 450 N BRAND BLVD GLENDALE CA 91203

Original CMS address: 450 N BRAND BLVD, STE 600, GLENDALE, CA, 912032349

**Verified.** Glendale returns an exact primary address point for 91203. Its street result is within 50 m. The CAMS 91340 record is in San Fernando and was rejected. Accepted location: 450 N BRAND BLVD, GLENDALE, CA, 91203 (Los Angeles County). [Evidence 1](https://gismap.glendaleca.gov/arcgis/rest/services/Common/CAD_SiteAddress_Street/GeocodeServer) [Evidence 2](https://gismap.glendaleca.gov/arcgis/rest/services/Common/CAD_SiteAddress_Street/GeocodeServer/findAddressCandidates?SingleLine=450+N+BRAND+BLVD%2C+GLENDALE%2C+CA%2C+91203&outFields=Addr_type%2CMatch_addr%2CAddNum%2CPostal&outSR=4326&f=pjson)

### 4510E PACIFIC COAST HWY 320 LONG BEACH CA 90804

Original CMS address: 4510E PACIFIC COAST HWY 320, LONG BEACH, CA, 908046926

**Verified.** Long Beach returns a score-100 primary address point matching house, street, direction and ZIP. Census locates the same civic address about 123 m away by street interpolation. The authoritative city point is used directly, without expanding the search radius. Suite 320 is not a separate mapped point. Accepted location: 4510 E PACIFIC COAST HWY, LONG BEACH, CA, 90804 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=4510+E+PACIFIC+COAST+HWY%2C+LONG+BEACH%2C+CA%2C+90804&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://gis.longbeach.gov/fed/rest/services/Locators/CLB_AddressPoints_WGS/GeocodeServer/findAddressCandidates?SingleLine=4510+E+PACIFIC+COAST+HWY%2C+LONG+BEACH%2C+CA%2C+90804&outFields=Addr_type%2CMatch_addr%2CAddNum%2CPostal&outSR=4326&f=pjson)

### 5301 LAUREL CANTON BL VALLEY VILLAGE CA 91607

Original CMS address: 5301 LAUREL CANTON BL., STE 201A, VALLEY VILLAGE, CA, 916072736

**Verified.** Historical CMS confirms Canyon and suite 201A. County CAMS and Census agree on the corrected street and ZIP within 30 m. The existing analysis row has the same corrected house number, street, ZIP and CAMS feature ID. Both registration keys refer to the same mapped address. Accepted location: 5301 LAUREL CANYON BLVD, VALLEY VILLAGE, CA 91607 (Los Angeles County). [Evidence 1](https://www.cms.gov/files/document/r12405otn.pdf) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=5301+LAUREL+CANYON+BLVD%2C+VALLEY+VILLAGE%2C+CA%2C+91607&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 3](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1767912&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 4](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272347017006%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 6345 BALBOA BLVD ENCINO CA 91316

Original CMS address: 6345 BALBOA BLVD, STE 315, ENCINO, CA, 913161500

**Verified.** The Assessor links the CAMS point to parcel 2230024006 and the original 91316 situs. LADBS independently confirms the civic address and ZIP. CAMS labels the parcel Van Nuys 91406, which is inconsistent with its assessor situs. Accepted location: 6345 BALBOA BLVD, ENCINO, CA 91316 (Los Angeles County). [Evidence 1](https://www.ladbsservices2.lacity.org/EBEWECompliance/Default/Index1?syear=2017) [Evidence 2](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1777020&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 3](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query?where=AIN%3D%272230024006%27&outFields=AIN%2CSitusFullAddress%2CCENTER_LAT%2CCENTER_LON&outSR=4326&f=pjson)

### 7233 1 2 FOOTHILL BLVD TUJUNGA CA 91042

Original CMS address: 7233 1/2 FOOTHILL BLVD.,, TUJUNGA, CA, 910422718

**Approximate.** The original fraction was restored for Census. The 7233 and 7233 1/2 interpolations coincide. CAMS supplies only the base address and the assessor lists another situs on that parcel, so fraction precision is unconfirmed. Accepted location: 7233 1/2 FOOTHILL BLVD, TUJUNGA, CA, 91042 (Los Angeles County). [Evidence 1](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0/query?where=OBJECTID%3D1696508&outFields=OBJECTID%2CFullAddress%2CAIN&outSR=4326&f=pjson) [Evidence 2](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=7233+1%2F2+FOOTHILL+BLVD%2C+TUJUNGA%2C+CA%2C+91042&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json)

### 726 W BROADWAY ST GLENDALE CA 91204

Original CMS address: 726 W BROADWAY ST, UNIT B, GLENDALE, CA, 912041054

**Verified.** The Glendale primary address point resolves the extra ST. CAMS supplies unit D rather than CMS unit B. Census and the municipal primary address corroborate the building location. Accepted location: 726 W BROADWAY, GLENDALE, CA, 91204 (Los Angeles County). [Evidence 1](https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=726+W+BROADWAY%2C+GLENDALE%2C+CA%2C+91204&benchmark=Public_AR_Current&vintage=Current_Current&layers=Counties&format=json) [Evidence 2](https://gismap.glendaleca.gov/arcgis/rest/services/Common/CAD_SiteAddress_Street/GeocodeServer/findAddressCandidates?SingleLine=726+W+BROADWAY%2C+GLENDALE%2C+CA%2C+91204&outFields=Addr_type%2CMatch_addr%2CAddNum%2CPostal&outSR=4326&f=pjson)

### 809 S LEMON AVE DIAMOND BAR CA 91789

Original CMS address: 809 S LEMON AVE, DIAMOND BAR, CA, 917892906

**Unmapped.** NPPES confirms the original 809 S Lemon and ZIP+4. Census interpolates 809 Lemon without S. The 100 m county check returned 835 Lemon at a Walnut situs, with no 809 point or parcel. The corroborating OSM South Lemon way is over 400 m from the Census estimate. The assessor's 809 E Lemon result is in Monrovia. This remains unmapped. [Original NPPES location](https://npiregistry.cms.hhs.gov/provider-view/1447517073) [OSM road segment](https://www.openstreetmap.org/way/406283319)
