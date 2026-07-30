"""
Mapper for ITSOPS SQL Data to GLPI Assets.
Provides mapping lookups and transformation helpers for ITSOPS -> GLPI migration
based on ITSOPS short codes and field mapping specifications.
"""

# Short code mapping for ITSOPS ITEM_TYPE to GLPI Asset Class / Endpoint (All map to CustomAsset INVENTORYAsset)
ITEM_TYPE_GLPI_MAPPING = {
    'BEA': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Beamer
    'CRT': 'Glpi\\CustomAsset\\INVENTORYAsset',  # CRT
    'DKS': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Dockingstation
    'EXT': 'Glpi\\CustomAsset\\INVENTORYAsset',  # External Peripheral
    'LAN': 'Glpi\\CustomAsset\\INVENTORYAsset',  # LAN
    'MOB': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Mobile Phone
    'NB':  'Glpi\\CustomAsset\\INVENTORYAsset',  # Laptop
    'PC':  'Glpi\\CustomAsset\\INVENTORYAsset',  # Computer
    'PHD': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Desk Peripheral
    'PRT': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Printer
    'SRV': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Server
    'SXT': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Peripheral Server
    'TAB': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Tablet
    'TEL': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Fix Phone
    'TFT': 'Glpi\\CustomAsset\\INVENTORYAsset',  # Screen
    'WAN': 'Glpi\\CustomAsset\\INVENTORYAsset',  # WAN
    'WS':  'Glpi\\CustomAsset\\INVENTORYAsset'   # Workstation
}

# Human-readable labels for ITSOPS ITEM_TYPE
ITEM_TYPE_LABEL_MAPPING = {
    'BEA': 'Beamer',
    'CRT': 'CRT',
    'DKS': 'Dockingstation',
    'EXT': 'External Peripheral',
    'LAN': 'LAN',
    'MOB': 'Mobile Phone',
    'NB':  'Laptop',
    'PC':  'Computer',
    'PHD': 'Desk Peripheral',
    'PRT': 'Printer',
    'SRV': 'Server',
    'SXT': 'Peripheral Server',
    'TAB': 'Tablet',
    'TEL': 'Fix Phone',
    'TFT': 'Screen',
    'WAN': 'WAN',
    'WS':  'Workstation'
}

# Human-readable labels for ITSOPS ITEM_USED_FOR
ITEM_USED_FOR_LABEL_MAPPING = {
    'BRW': 'Loan',
    'CMD': 'Ordered',
    'CNT': 'Contractor',
    'DES': 'Stock Deletion',
    'DSG': 'Desk Sharing',
    'INS': 'Infrastructure',
    'LSF': 'Lost Forever',
    'LST': 'Lost',
    'OTH': 'Other',
    'PRO': 'Project',
    'PRP': 'In Preparation',
    'PRS': 'Proposed',
    'PWS': 'Personal Equipment',
    'RFS': 'Refused',
    'RIP': 'Renew In Progress',
    'RMA': 'RMA',
    'RNT': 'Rented',
    'RTN': 'Stock Return',
    'RTU': 'Resell To User',
    'SAL': 'Stock Resell',
    'SIC': 'Sold Interco',
    'SPR': 'Stock Spare',
    'STK': 'Stock',
    'STV': 'Stock For Vietnam',
    'SVN': 'Vietnam Workstation',
    'UKN': 'Unknow',
    'VST': 'Guest',
    'WST': 'Workplace'
}


def get_glpi_item_type(itsops_type):
    """
    Maps ITSOPS ITEM_TYPE code to a GLPI endpoint class.
    In this GLPI installation, all assets are managed under Glpi\\CustomAsset\\INVENTORYAsset.
    """
    return 'Glpi\\CustomAsset\\INVENTORYAsset'


def get_item_type_label(itsops_type):
    """
    Returns the human-readable description for an ITSOPS ITEM_TYPE code.
    """
    if not itsops_type:
        return ''
    code = str(itsops_type).strip().upper()
    return ITEM_TYPE_LABEL_MAPPING.get(code, code)


def get_item_used_for_label(used_for_code):
    """
    Returns the human-readable description for an ITSOPS ITEM_USED_FOR short code.
    """
    if not used_for_code:
        return ''
    code = str(used_for_code).strip().upper()
    return ITEM_USED_FOR_LABEL_MAPPING.get(code, code)


def map_status(status_str):
    """
    Map raw status or short code to GLPI state name. Defaults to Stock.
    """
    if not status_str:
        return 'Stock'
    s = str(status_str).strip()
    return ITEM_USED_FOR_LABEL_MAPPING.get(s.upper(), s)


def map_item_to_glpi(row):
    """
    Maps a dictionary row from dbo._ITEM to a GLPI payload.
    Returns: (glpi_item_type, payload_dict)
    """
    itsops_type = str(row.get('ITEM_TYPE') or '').strip().upper()
    glpi_type = get_glpi_item_type(itsops_type)
    
    item_number = str(row.get('ITEM_NUMBER') or '').strip()
    item_model = str(row.get('ITEM_MODEL') or '').strip()
    
    # Asset Name rule: Asset type code + Inventory number
    if itsops_type and item_number:
        name = f"{itsops_type}{item_number}"
    else:
        name = item_model or item_number or "Unknown"
        
    comment_parts = ["Migrated from ITSOPS."]
    owner = str(row.get('ITEM_OWNER') or '').strip()
    if owner:
        comment_parts.append(f"Owner: {owner}")
    constructor = str(row.get('ITEM_CONSTRUCTOR') or '').strip()
    if constructor:
        comment_parts.append(f"Constructor: {constructor}")
    os_str = str(row.get('ITEM_OS') or '').strip()
    if os_str:
        comment_parts.append(f"OS: {os_str}")
        
    payload = {
        "name": name,
        "serial": str(row.get('ITEM_SERIAL_NUMBER') or '').strip(),
        "otherserial": item_number,
        "comment": "\n".join(comment_parts)
    }
    
    return glpi_type, payload
