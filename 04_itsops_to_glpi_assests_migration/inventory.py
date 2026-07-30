"""
Inventory management migration module for ITSOPS to GLPI.
Handles mapping, extraction, and ingestion of SearchBox, Items, and Oracle Synchronization features.
"""
import logging
from mapper import get_glpi_item_type, get_item_type_label, map_status, get_item_used_for_label

logger = logging.getLogger(__name__)

def safe_str(val, default=""):
    """
    Safely convert a value to string, handling None and placeholder strings ('None', 'null', 'n/a', '-', etc.).
    """
    if val is None:
        return default
    s = str(val).strip()
    if s.lower() in ("none", "null", "n/a", "-", "unknown"):
        return default
    return s

def resolve_dropdown(glpi_client, endpoint_type, name, auto_create=False):
    """
    Resolve a dropdown item ID in GLPI by name. Optionally auto-creates if not found.
    """
    name = safe_str(name)
    if not name or not glpi_client:
        return None
    try:
        item_id = glpi_client.get_item_id(endpoint_type, name)
        if item_id:
            return item_id
        if auto_create:
            logger.info(f"Auto-creating {endpoint_type}: {name}")
            return glpi_client.create_item(endpoint_type, {"name": name})
        else:
            logger.warning(f"Missing predefined {endpoint_type}: {name}")
            return None
    except Exception as e:
        logger.error(f"Error resolving dropdown {endpoint_type} '{name}': {e}")
        return None

def resolve_user_id(glpi_client, user_str):
    """
    Resolve a user ID from email or username string.
    """
    user_str = safe_str(user_str)
    if not user_str or not glpi_client:
        return None
    try:
        # Check if email
        if "@" in user_str:
            uid = glpi_client.get_user_id_by_email(user_str)
            if uid:
                return uid
        # Fallback to get_item_id on User
        return glpi_client.get_item_id("User", user_str)
    except Exception as e:
        logger.error(f"Error resolving user '{user_str}': {e}")
        return None

def resolve_location_id(glpi_client, location_str):
    """
    Resolve or create location ID.
    """
    location_str = safe_str(location_str)
    if not location_str or not glpi_client:
        return None
    try:
        loc_id = glpi_client.get_location_id(location_str)
        if loc_id:
            return loc_id
        direct_id = glpi_client.get_item_id("Location", location_str)
        if direct_id:
            return direct_id
        logger.info(f"Auto-creating Location: {location_str}")
        new_id = glpi_client.create_item("Location", {"name": location_str})
        if new_id and hasattr(glpi_client, 'location_cache'):
            glpi_client.location_cache[location_str.lower()] = new_id
        return new_id
    except Exception as e:
        logger.error(f"Error resolving location '{location_str}': {e}")
        return None

def map_inventory_item(row, glpi_client=None):
    """
    Map an ITSOPS dbo._ITEM row dictionary to GLPI main payload and auxiliary payloads.
    Returns: (glpi_type, main_payload, aux_payloads)
    """
    itsops_type = safe_str(row.get('ITEM_TYPE'))
    glpi_type = get_glpi_item_type(itsops_type)
    
    item_number = safe_str(row.get('ITEM_NUMBER'))
    item_model = safe_str(row.get('ITEM_MODEL'))
    
    # Format name: ITEM_TYPE + ITEM_NUMBER, fallback to model or number
    if itsops_type and item_number:
        name = f"{itsops_type}{item_number}"
    else:
        name = item_model or item_number or "Unknown"
        
    serial = safe_str(row.get('ITEM_SERIAL_NUMBER'))
    otherserial = item_number
    owner_str = safe_str(row.get('ITEM_OWNER'))
    
    users_id = resolve_user_id(glpi_client, row.get('EMPLOYEE_VISA') or row.get('EMPLOYEE_EMAIL') or row.get('ITEM_USER'))
    locations_id = resolve_location_id(glpi_client, row.get('ITEM_LOCATION_BAT'))
    manufacturers_id = resolve_dropdown(glpi_client, "Manufacturer", row.get('ITEM_CONSTRUCTOR'), auto_create=True)
    
    raw_status = safe_str(row.get('ITEM_USED_FOR')) or safe_str(row.get('ITEM_STATUS')) or safe_str(row.get('ITEM_STATE'))
    mapped_status = map_status(raw_status) if raw_status else "Stock"
    states_id = resolve_dropdown(glpi_client, "State", mapped_status, auto_create=True)
    
    if glpi_type == "Glpi\\CustomAsset\\INVENTORYAsset":
        type_endpoint = "Glpi\\CustomAsset\\INVENTORYAssetType"
        model_endpoint = "Glpi\\CustomAsset\\INVENTORYAssetModel"
        type_field = "assets_assettypes_id"
        model_field = "assets_assetmodels_id"
        type_label = get_item_type_label(itsops_type) or itsops_type
        types_id = resolve_dropdown(glpi_client, type_endpoint, type_label, auto_create=True)
        models_id = resolve_dropdown(glpi_client, model_endpoint, item_model, auto_create=True)
    else:
        type_endpoint = f"{glpi_type}Type"
        model_endpoint = f"{glpi_type}Model"
        type_field = f"{glpi_type.lower()}types_id"
        model_field = f"{glpi_type.lower()}models_id"
        types_id = resolve_dropdown(glpi_client, type_endpoint, itsops_type, auto_create=True)
        models_id = resolve_dropdown(glpi_client, model_endpoint, item_model, auto_create=True)
    
    constructor_str = safe_str(row.get('ITEM_CONSTRUCTOR'))
    os_str = safe_str(row.get('ITEM_OS'))
    comment = "ITSOPS-Import"
    
    main_payload = {
        "name": name,
        "comment": comment
    }
    if serial:
        main_payload["serial"] = serial
    if otherserial:
        main_payload["otherserial"] = otherserial
    if users_id is not None:
        main_payload["users_id"] = users_id
    if locations_id is not None:
        main_payload["locations_id"] = locations_id
    if manufacturers_id is not None:
        main_payload["manufacturers_id"] = manufacturers_id
    if states_id is not None:
        main_payload["states_id"] = states_id
    if types_id is not None:
        main_payload[type_field] = types_id
    if models_id is not None:
        main_payload[model_field] = models_id
        
    autoupdatesystems_id = resolve_dropdown(glpi_client, "AutoUpdateSystem", "ITSOPS-MIGRATION", auto_create=True)
    if autoupdatesystems_id is not None:
        main_payload["autoupdatesystems_id"] = autoupdatesystems_id
        
    if glpi_type == "Glpi\\CustomAsset\\INVENTORYAsset":
        main_payload["assets_assetdefinitions_id"] = 17
        loc_off = safe_str(row.get('EMPLOYEE_LOCATION'))
        main_payload["custom_user_office_location"] = loc_off
        if owner_str:
            owner_id = resolve_dropdown(glpi_client, "Glpi\\CustomDropdown\\InventoryOwnerDropdown", owner_str, auto_create=True)
            if owner_id is not None:
                main_payload["custom_invetory_onwer"] = owner_id
        
    aux_payloads = {}
    
    # Technical Specification (ID 21)
    tech_spec = {}
    proc = safe_str(row.get('ITEM_PROCESSOR'))
    proc_model = safe_str(row.get('ITEM_PROCESSOR_MODEL'))
    proc_full = " - ".join(filter(None, [proc, proc_model])) if proc or proc_model else ""
    if proc_full: tech_spec['processorfield'] = proc_full
    ram = safe_str(row.get('ITEM_WORK_MEM'))
    if ram: tech_spec['ramfield'] = ram
    hdd = safe_str(row.get('ITEM_STORAGE_MEM'))
    if hdd: tech_spec['harddrivefield'] = hdd
    orcl_id = safe_str(row.get('ORC_AssetId'))
    if orcl_id: tech_spec['oracleassetidfield'] = orcl_id
    orcl_num = safe_str(row.get('ORC_AssetNumber'))
    if orcl_num: tech_spec['oracleassetnumberfield'] = orcl_num
    if tech_spec:
        aux_payloads['technical_spec'] = tech_spec
        
    # Renewing (ID 23)
    renewing = {}
    warr_exp = safe_str(row.get('ITEM_WARRANTY_EXPIRY_DATE'))
    if warr_exp: renewing['warrantyexpirationfield'] = warr_exp
    ren_state = safe_str(row.get('ITEM_RENEWAL'))
    if ren_state: renewing['renewalstatefield'] = ren_state
    if renewing:
        aux_payloads['renewing'] = renewing
        
    # ITSOPS Log (ID 24)
    moditem_json_str = safe_str(row.get('MODITEM_JSON'))
    if moditem_json_str:
        try:
            import json
            logs = json.loads(moditem_json_str)
            html = '<table class="table" style="box-sizing: border-box; border-spacing: 0px; border-collapse: collapse; background-color: transparent; width: 100%; max-width: 100%; margin-bottom: 20px; color: #333333; font-family: \'Open Sans\', sans-serif; font-size: 13px;">'
            html += '<thead style="box-sizing: border-box;"><tr style="box-sizing: border-box;">'
            th_style = 'box-sizing: border-box; padding: 4px; text-align: left; vertical-align: bottom; border-top: 0px; border-bottom: 1px solid #eeeeee; color: #555555; font-weight: bold; font-size: 11px; text-transform: uppercase;'
            html += f'<th style="{th_style}">USER</th><th style="{th_style}">DATE</th><th style="{th_style}">DATABASE FIELD</th><th style="{th_style}">OBJECT</th><th style="{th_style}">PREVIOUS VALUE</th><th style="{th_style}">NEW VALUE</th><th style="{th_style}">REASON</th>'
            html += '</tr></thead><tbody style="box-sizing: border-box;">'
            
            field_obj_map = {
                "ITEM_USED_FOR": "Used for",
                "ITEM_LOCATION_BAT": "Site location",
                "ITEM_LOCATION_OFF": "Office location",
                "ITEM_USER": "User's visa",
                "ITEM_FREE_REM_1": "Text information",
                "ITEM_CHECKINV": "Check inventory",
                "ITEM_BUY_DATE": "Buy date",
                "ITEM_INVOICE": "Invoice number",
                "ITEM_USER_ID": "User ID",
                "ITEM_PRICE": "Item's price",
                "ITEM_SERIAL_NUMBER": "Serial number",
                "ITEM_RENT_NUMBER": "Rental number",
                "ITEM_OS": "Operational System",
                "ITEM_RENEWAL": "Renewal state",
                "ITEM_WORK_MEM": "Hard drive capacity",
                "ITEM_RENEWAL_STATUS": "Renewal status",
                "Dummy_Boolean": "Renewal state",
                "ITEM_RENT_TICKET_NB": "Rental ticket number",
                "ITEM_MODEL": "Model",
                "ITEM_WARRANTY": "Warranty",
                "ITEM_PURCHASE_ORDER": "Purchase order",
                "ITEM_MAC_ADDRESS": "MAC address",
                "ITEM_TEMP_VISA": "Temp visa",
                "ITEM_ACCESSORIES": "Accessories",
                "ITEM_STORAGE_MEM": "Storage memory",
                "ITEM_RENEWAL_YEAR": "Renewal year",
                "ITEM_PROCESSOR": "Processor",
                "ITEM_WARRANTY_EXPIRY_DATE": "Warranty expiration date",
                "ITEM_CONSTRUCTOR": "Constructor",
                "ITEM_RENTAL_ID": "Rental ID",
                "ITEM_OWNER": "Owner (Society)",
                "ITEM_SERVICE_NB": "Service number",
                "ITEM_VENDOR": "Vendor",
                "ITEM_TYPE": "Type",
                "ITEM_CAPACITY": "Capacity",
                "ITEM_NUMBER": "Asset number (ID)",
                "ITEM_LAST_UPDATE_REASON": "Last update reason",
            }
            
            td_style = 'box-sizing: content-box; padding: 4px; border-radius: 0px !important; line-height: 1.42857; vertical-align: middle; border-width: 0px 0px 1px; border-style: none none solid; border-color: currentcolor currentcolor #f2f5f8; background: none #eeeeee; color: #8896a0;'
            span_style = 'box-sizing: border-box; border-radius: 0.25em; display: inline; padding: 0px 4px 1px; font-size: 12px; font-weight: 300; line-height: 1; color: #ffffff; text-align: center; white-space: nowrap; vertical-align: baseline; background-color: #45b6af; font-family: \'Open Sans\', sans-serif; text-shadow: none !important;'
            
            def format_log_val(val):
                if val is None: return "null"
                val_str = str(val).strip()
                return "null" if val_str.lower() == "null" else val_str
                
            for log in logs:
                db_field = format_log_val(log.get('MODITEM_FIELD'))
                if db_field == "null":
                    obj_name = "null"
                else:
                    obj_name = field_obj_map.get(db_field, db_field.replace('ITEM_', '').replace('_', ' ').capitalize())
                
                old_val = format_log_val(log.get("MODITEM_OLDVALUE"))
                new_val = format_log_val(log.get("MODITEM_NEWVALUE"))
                
                if db_field == 'ITEM_USED_FOR':
                    old_val = get_item_used_for_label(old_val)
                    new_val = get_item_used_for_label(new_val)
                    
                html += f'<tr style="box-sizing: border-box;">'
                html += f'<td style="{td_style}">{safe_str(log.get("MODITEM_USER"))}</td>'
                html += f'<td style="{td_style}">{safe_str(log.get("MODITEM_DATE"))[:10]}</td>'
                html += f'<td style="{td_style}">{db_field}</td>'
                html += f'<td style="{td_style}">{obj_name}</td>'
                html += f'<td style="{td_style}">{old_val}</td>'
                html += f'<td style="{td_style}">{new_val}</td>'
                html += f'<td style="{td_style}"><span class="label label-sm label-success" style="{span_style}">{safe_str(log.get("MODITEM_REASON"))}</span></td>'
                html += f'</tr>'
            html += '</tbody></table>'
            log_str = html
        except Exception as e:
            logger.error(f"Error parsing MODITEM_JSON: {e}")
            log_str = safe_str(row.get('ITEM_LOG') or row.get('ITSOP_LOG'))
            if not log_str and comment == "ITSOPS-Import":
                log_str = "<p>Imported from ITSOPS script.</p>"
    else:
        log_str = safe_str(row.get('ITEM_LOG') or row.get('ITSOP_LOG'))
        if not log_str and comment == "ITSOPS-Import":
            log_str = "<p>Imported from ITSOPS script.</p>"
    if log_str:
        aux_payloads['itsops_log'] = {'itsoplogfield': log_str}
        
    # Infocom
    infocom = {}
    vendor_str = safe_str(row.get('ITEM_VENDOR'))
    suppliers_id = resolve_dropdown(glpi_client, "Supplier", vendor_str, auto_create=True)
    if suppliers_id is not None:
        infocom['suppliers_id'] = suppliers_id
    buy_date = safe_str(row.get('ITEM_BUY_DATE'))
    if buy_date: infocom['buy_date'] = buy_date
    po_num = safe_str(row.get('ITEM_PURCHASE_ORDER'))
    if po_num: infocom['order_number'] = po_num
    inv_num = safe_str(row.get('ITEM_INVOICE'))
    if inv_num: infocom['bill'] = inv_num
    price = safe_str(row.get('ITEM_PRICE'))
    if price:
        cleaned_price = price.replace('$', '').replace('€', '').replace(',', '').strip()
        if cleaned_price:
            infocom['value'] = cleaned_price
    immo = safe_str(row.get('ITEM_RENTAL_NUMBER'))
    if immo: infocom['immo_number'] = immo
    warr_dur = safe_str(row.get('ITEM_WARRANTY'))
    if warr_dur: 
        try:
            infocom['warranty_duration'] = int(float(warr_dur)) * 12
        except ValueError:
            infocom['warranty_duration'] = warr_dur
    if infocom:
        aux_payloads['infocom'] = infocom
        
    return glpi_type, main_payload, aux_payloads

def extract_inventory_items(sql_client, limit=None, item_id=None, start_after_id=None, schema="dbo", batch_size=1000, shared_erp_db=None):
    """
    Extract rows from dbo._ITEM using fetchmany/yield pattern to preserve memory.
    Supports resuming via start_after_id.
    """
    if not schema.isidentifier():
        raise ValueError(f"Invalid database schema name: {schema}")
    if not shared_erp_db:
        raise ValueError("shared_erp_db must be provided in configuration")
        
    query = f"""
        SELECT {'TOP ' + str(limit) if limit else ''} 
            i.*,
            CASE 
                WHEN i.ITEM_USED_FOR = 'PWS' THEN ldap.physicalDeliveryOfficeName
                ELSE i.ITEM_LOCATION_OFF
            END AS EMPLOYEE_LOCATION,
            e.Visa AS EMPLOYEE_VISA,
            e.Email AS EMPLOYEE_EMAIL,
            (SELECT MODITEM_USER, MODITEM_DATE, MODITEM_FIELD, MODITEM_OLDVALUE, MODITEM_NEWVALUE, MODITEM_REASON 
             FROM [{schema}].[MODITEM] m 
             WHERE m.ITEM_ID = i.ITEM_ID 
             ORDER BY MODITEM_DATE DESC 
             FOR JSON AUTO) as MODITEM_JSON
        FROM [{schema}].[_ITEM] i
        OUTER APPLY (
            SELECT TOP 1 Visa, Email
            FROM [{schema}].[Employee_View] ev
            WHERE ev.Id = i.ITEM_USER_ID
        ) e
        OUTER APPLY (
            SELECT TOP 1 physicalDeliveryOfficeName
            FROM [{shared_erp_db}].[dbo].[LDAP_Users] lu
            WHERE lu.sAMAccountName = e.Visa
            ORDER BY lu.whenChanged DESC
        ) ldap
    """
    where_clauses = []
    if item_id:
        where_clauses.append(f"i.ITEM_ID = {int(item_id)}")
    if start_after_id:
        where_clauses.append(f"i.ID > {int(start_after_id)}")
    
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += "\n        ORDER BY i.ID\n    "
    
    cursor = sql_client.conn.cursor()
    try:
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield dict(zip(columns, row))
    finally:
        cursor.close()

def ingest_inventory_item(glpi_client, glpi_type, main_payload, aux_payloads):
    """
    Ingest main asset and auxiliary plugin/infocom items into GLPI.
    Returns asset_id if created successfully, else None.
    """
    try:
        asset_id = glpi_client.create_item(glpi_type, main_payload)
        if not asset_id:
            logger.error(f"Failed to create main asset {glpi_type}: {main_payload.get('name')}")
            return None
            
        logger.info(f"Successfully created {glpi_type} ID: {asset_id}")
        
        # Ingest Infocom
        if 'infocom' in aux_payloads and aux_payloads['infocom']:
            info_payload = dict(aux_payloads['infocom'])
            info_payload['items_id'] = asset_id
            info_payload['itemtype'] = glpi_type
            glpi_client.create_item("Infocom", info_payload)
            
        # Ingest Technical Specification PluginField
        if 'technical_spec' in aux_payloads and aux_payloads['technical_spec']:
            tech_payload = dict(aux_payloads['technical_spec'])
            tech_payload['items_id'] = asset_id
            tech_payload['itemtype'] = glpi_type
            endpoint = "PluginFieldsGlpicustomassetinventoryassetInvetorytecspec" if glpi_type == "Glpi\\CustomAsset\\INVENTORYAsset" else f"PluginFields{glpi_type}Technicalspecification"
            glpi_client.create_item(endpoint, tech_payload)
            
        # Ingest Renewing PluginField
        if 'renewing' in aux_payloads and aux_payloads['renewing']:
            ren_payload = dict(aux_payloads['renewing'])
            ren_payload['items_id'] = asset_id
            ren_payload['itemtype'] = glpi_type
            endpoint = "PluginFieldsGlpicustomassetinventoryassetRenewing" if glpi_type == "Glpi\\CustomAsset\\INVENTORYAsset" else f"PluginFields{glpi_type}Renewing"
            glpi_client.create_item(endpoint, ren_payload)
            
        # Ingest ITSOPS Log PluginField
        if 'itsops_log' in aux_payloads and aux_payloads['itsops_log']:
            log_payload = dict(aux_payloads['itsops_log'])
            log_payload['items_id'] = asset_id
            log_payload['itemtype'] = glpi_type
            endpoint = "PluginFieldsGlpicustomassetinventoryassetItsopslog" if glpi_type == "Glpi\\CustomAsset\\INVENTORYAsset" else f"PluginFields{glpi_type}Itsopslog"
            glpi_client.create_item(endpoint, log_payload)
            
        return asset_id
    except Exception as e:
        logger.error(f"Error ingesting item {main_payload.get('name')}: {e}")
        return None
