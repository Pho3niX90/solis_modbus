# solis_config.py

SOLIS_INVERTERS = {
    "Grid-Tied Inverters": {
        "Single Phase": [
            {"model": "S6-GR1P(0.7-3.6)K-M", "wattage": [700, 1000, 1500, 2000, 2500, 3000, 3600], "phases": 1},
            {"model": "S6-GR1P(2.5-6)K-S", "wattage": [2500, 3000, 3600, 4000, 4600, 5000, 6000], "phases": 1},
            {"model": "S6-GR1P(2.5-6)K", "wattage": [2500, 3000, 3600, 4000, 4600, 5000, 6000], "phases": 1},
            {"model": "S6-GR1P(7-8)K2", "wattage": [7000, 8000], "phases": 1},
            {"model": "S6-GR1P(7-10)K03-NV-ND", "wattage": [7000, 8000, 9000, 10000], "phases": 1},
            {"model": "S5-GR1P(7-10)K", "wattage": [7000, 8000, 9000, 10000], "phases": 1},
            {"model": "Solis-Mini(700-3600)-4G", "wattage": [700, 1000, 1500, 2000, 2500, 3000, 3600], "phases": 1},
            {"model": "Solis-1P(2.5-6)K-4G", "wattage": [2500, 3000, 3600, 4000, 4600, 5000, 6000], "phases": 1},
            {"model": "Solis-1P(7-8)K-5G", "wattage": [7000, 8000], "phases": 1},
            {"model": "Solis-1P(9-10)K-4G", "wattage": [9000, 10000], "phases": 1},
        ],
        "Three Phase": [
            {"model": "S5-GR3P(3-20)K", "wattage": [3000, 4000, 5000, 6000, 8000, 9000, 10000, 12000, 13000, 15000, 17000, 20000], "phases": 3},
            {"model": "S5-GR3P(5-10)K-LV", "wattage": [5000, 6000, 8000, 9000, 10000], "phases": 3},
        ]
    },
    "Hybrid Inverters": {
        "Single Phase": [
            {"model": "S6-EH1P(3-6)K-L-PRO", "wattage": [3000, 3600, 5000, 6000], "phases": 1},
            {"model": "S6-EH1P(3-8)K-L-PLUS", "wattage": [3000, 3600, 5000, 6000, 8000], "phases": 1},
            {"model": "S6-EH1P8K-L-PRO", "wattage": [8000], "phases": 1},
            {"model": "S6-EO1P(4-5)K-48", "wattage": [4000, 5000], "phases": 1},
            {"model": "S5-EO1P(4-5)K-48", "wattage": [4000, 5000], "phases": 1},
            {"model": "RHI-(3-6)K-48ES-5G", "wattage": [3000, 3600, 5000, 6000], "phases": 1},
        ],
        "Three Phase": [
            {"model": "S6-EH3P(8-15)K02-NV-YD-L", "wattage": [8000, 10000, 12000, 15000], "phases": 3},
            {"model": "S6-EH3P(12-20)K-H", "wattage": [12000, 15000, 20000], "phases": 3},
            {"model": "S6-EH3P(30-50)K-H", "wattage": [30000, 35000, 40000, 45000, 50000], "phases": 3},
            {"model": "S6-EH3P30K-H-LV", "wattage": [30000], "phases": 3},
            {"model": "RHI-3P(5-10)K-HVES-5G", "wattage": [5000, 6000, 8000, 9000, 10000], "phases": 3},
        ]
    },
    "String Inverters": {
        "Three Phase": [
            {"model": "S6-GC3P(150-200)K07-ND", "wattage": [150000, 160000, 180000, 200000], "phases": 3},
            {"model": "S6-GU350K-EHV", "wattage": [350000], "phases": 3},
            {"model": "Solis-(215-255)K-EHV-5G", "wattage": [215000, 220000, 225000, 230000, 235000, 240000, 245000, 250000, 255000], "phases": 3},
        ]
    }
}
