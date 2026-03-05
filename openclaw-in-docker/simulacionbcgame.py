import random

def simulate_strategy(
    sesiones=1000,
    rondas_por_sesion=10000,
    win_probability=0.495,
    banca_inicial=0
):
    
    resultados = []
    max_apuesta_global = 0
    max_banca_necesaria = 0
    max_ganancia_global = float('-inf')
    max_perdida_global = float('inf')
    max_drawdown_global = 0

    for _ in range(sesiones):
        
        bankroll = banca_inicial
        apuesta = 1
        contador_win = 0
        
        pico_bankroll = bankroll
        peor_drawdown = 0
        
        for _ in range(rondas_por_sesion):
            
            max_apuesta_global = max(max_apuesta_global, apuesta)
            
            if random.random() < win_probability:
                resultado = 'WIN'
            else:
                resultado = 'LOSE'
            
            if resultado == 'WIN':
                bankroll += apuesta
                contador_win += 1
                
                if contador_win == 2:
                    # Se cierra ciclo
                    contador_win = 0
                    apuesta = 1
                else:
                    apuesta *= 2  # reinvertir ganancia
            
            else:  # LOSE
                bankroll -= apuesta
                contador_win = 0
                apuesta += 1  # progresión lineal
            
            # Actualizar métricas
            pico_bankroll = max(pico_bankroll, bankroll)
            drawdown = pico_bankroll - bankroll
            peor_drawdown = max(peor_drawdown, drawdown)
            
            max_banca_necesaria = max(max_banca_necesaria, abs(bankroll))
        
        resultados.append(bankroll)
        max_ganancia_global = max(max_ganancia_global, bankroll)
        max_perdida_global = min(max_perdida_global, bankroll)
        max_drawdown_global = max(max_drawdown_global, peor_drawdown)
    
    print("==== RESULTADOS DEL EXPERIMENTO ====")
    print(f"Sesiones simuladas: {sesiones}")
    print(f"Promedio resultado final: {sum(resultados)/len(resultados):.2f}")
    print(f"Máxima ganancia obtenida: {max_ganancia_global}")
    print(f"Máxima pérdida obtenida: {max_perdida_global}")
    print(f"Apuesta máxima alcanzada: {max_apuesta_global}")
    print(f"Máxima banca necesaria: {max_banca_necesaria}")
    print(f"Máximo drawdown: {max_drawdown_global}")
    

# Ejecutar simulación
simulate_strategy(
    sesiones=1000,
    rondas_por_sesion=5000
)
