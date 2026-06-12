# status_mapping.py
#
# Status register 33095 reports fault codes whose HEX representation is the
# alarm code shown on the inverter display and in SolisCloud: register value
# 4112 (0x1010) is SolisCloud alarm "1010" / OV-G-V (grid overvoltage).
# Keys are the decimal register values; comments show the hex / SolisCloud code.
# See https://github.com/Pho3niX90/solis_modbus/issues/404.

STATUS_MAPPING = {
    # Operating states
    0: "Normal operation",
    1: "Open loop operation",
    2: "Waiting",
    3: "Generating",
    4: "Bypass / Inverting / Running",
    5: "Bypass / Inverting / Synchronize",
    6: "Bypass / Grid / Running",
    7: "Standby",
    8: "Derating",
    10: "Auto test",
    12: "Parameter setting",
    13: "Firmware updating",
    14: "Timed charge",
    15: "Generating",
    16: "Timed discharge",
    # 0x100x
    4096: "Stop",  # 0x1000
    4100: "Control off-Grid",  # 0x1004
    4111: "Islanding fault",  # 0x100F
    # 0x101x — grid faults
    4112: "Grid overvoltage",  # 0x1010 OV-G-V
    4113: "Grid undervoltage",  # 0x1011 UN-G-V
    4114: "Grid overfrequency",  # 0x1012 OV-G-F
    4115: "Grid underfrequency",  # 0x1013 UN-G-F
    4116: "Grid impedance is too large",  # 0x1014 G-IMP
    4117: "No Grid",  # 0x1015 NO-Grid
    4118: "Grid imbalance",  # 0x1016 G-PHASE
    4119: "Grid frequency jitter",  # 0x1017 G-F-FLU
    4120: "Grid overcurrent",  # 0x1018 OV-G-I
    4121: "Grid current tracking fault",  # 0x1019 IGFOL-F
    # 0x102x — DC faults
    4128: "DC overvoltage",  # 0x1020 OV-DC
    4129: "DC bus overvoltage",  # 0x1021 OV-BUS
    4130: "DC busbar uneven voltage",  # 0x1022 UNB-BUS
    4131: "DC bus undervoltage",  # 0x1023 UN-BUS
    4132: "DC busbar uneven voltage 2",  # 0x1024 UNB2-BUS
    4133: "DC A way overcurrent",  # 0x1025 OV-DCA-I
    4134: "DC B path overcurrent",  # 0x1026 OV-DCB-I
    4135: "DC input disturbance",  # 0x1027 DC-INTF
    4136: "DC reverse polarity",  # 0x1028
    4137: "PV midpoint grounding",  # 0x1029
    # 0x103x — device protection
    4144: "Grid disturbance",  # 0x1030 GRID-INTF
    4145: "DSP initialization malfunction protection",  # 0x1031 INI-FAULT
    4146: "Temperature protection",  # 0x1032 OV-TEM
    4147: "Ground protection",  # 0x1033 PV ISO-PRO / ground fault
    4148: "Leakage current fault",  # 0x1034 ILeak-PRO
    4149: "Relay failure",  # 0x1035 RelayChk-FAIL
    4150: "DSP_B failure protection",  # 0x1036 DSP-B-FAULT
    4151: "DC component is too large",  # 0x1037 DCInj-FAULT
    4152: "12V undervoltage fault protection",  # 0x1038 12Power-FAULT
    4153: "Leakage current self-test protection",  # 0x1039 ILeak-Check
    4154: "Under temperature protection",  # 0x103A UN-TEM
    # 0x104x — DSP / arc faults
    4160: "Arc self-test protection",  # 0x1040 AFCI-Check
    4161: "Arc malfunction protection",  # 0x1041 AFCI-FAULT
    4162: "DSP on-chip SRAM exception",  # 0x1042
    4163: "DSP on-chip FLASH exception",  # 0x1043
    4164: "DSP on-chip PC pointer is abnormal",  # 0x1044
    4165: "DSP key register exception",  # 0x1045
    4166: "Grid disturbance 02",  # 0x1046
    4167: "Grid current sampling abnormality",  # 0x1047
    4168: "IGBT overcurrent",  # 0x1048
    # 0x105x — battery / bypass faults
    4176: "Network side current transient",  # 0x1050
    4177: "Battery overvoltage hardware failure",  # 0x1051
    4178: "LLC hardware overcurrent",  # 0x1052
    4179: "Battery overvoltage detection",  # 0x1053
    4180: "Battery undervoltage detection",  # 0x1054
    4181: "Battery no connected",  # 0x1055
    4182: "Bypass overvoltage fault",  # 0x1056
    4183: "Bypass overload fault",  # 0x1057
    4184: "DSP self-check error",  # 0x1058
    # 0x106x — forced battery states
    4192: "Battery force charging",  # 0x1060
    4193: "Battery force discharging",  # 0x1061
    # 0x201x — communication / safety faults
    8208: "Fail safe",  # 0x2010
    8209: "Meter communication failure",  # 0x2011
    8210: "Battery communication failure (BMS)",  # 0x2012
    8211: "BMS firmware updating",  # 0x2013
    8212: "DSP communication failure",  # 0x2014
    8213: "BMS alarm",  # 0x2015
    8214: "Battery name failure",  # 0x2016 BatName-FAIL
    8215: "BMS alarm 2",  # 0x2017
    8216: "DRM connection failure",  # 0x2018
    8217: "Meter select failure",  # 0x2019
    # 0x202x
    8224: "Lead-acid battery high temperature",  # 0x2020
    8225: "Lead-acid battery low temperature",  # 0x2021
    # 0xF01x
    61456: "Grid surge",  # 0xF010
    61457: "Fan fault",  # 0xF011
}
