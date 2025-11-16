from dataclasses import dataclass
from typing import Tuple, Dict, Optional, List, Set
import heapq
import copy
import math
import time

@dataclass(frozen=True)
class Container:
    id: int
    weight: int
    destination: int
    position: Tuple[int, int]


@dataclass
class ProblemSpec:
    a: int  
    b: int  
    X: int  
    containers: Dict[int, Container]  
    D: int  


@dataclass(frozen=True)
class State:
    yard_grid: Tuple[Tuple[int, ...], ...]
    ship_grid: Tuple[Tuple[int, ...], ...]
    weight_left: int
    weight_right: int



def grid_to_tuple(grid: List[List[int]]) -> Tuple[Tuple[int, ...], ...]:
    return tuple(tuple(row) for row in grid)


def tuple_to_grid(t: Tuple[Tuple[int, ...], ...]) -> List[List[int]]:
    return [list(row) for row in t]


def ship_zone(column: int, b: int, D: int) -> int:
    cols_per_zone = b / D
    z = int(math.floor(column / cols_per_zone)) + 1
    if z < 1:
        z = 1
    if z > D:
        z = D
    return z


def get_left_right_columns(b: int) -> Tuple[Set[int], Set[int]]:
    left_end = (b - 1) // 2
    left_cols = set(range(0, left_end + 1))
    right_cols = set(range(left_end + 1, b))
    return left_cols, right_cols



def loading_cost(X: int, ry: int, cy: int, rs: int, cs: int) -> int:
    return X + abs(ry - rs) + abs(cy - cs)


def destination_penalty_for_position(cs: int, container_dest: int, b: int, D: int) -> int:
    zone = ship_zone(cs, b, D)
    return abs(zone - container_dest)


def imbalance_penalty(weight_left: int, weight_right: int) -> int:
    return abs(weight_left - weight_right)



#ACTION
def apply_action(state: State, problem: ProblemSpec, container_id: int, rs: int, cs: int) -> Tuple[State, int]:
    a, b, X, D = problem.a, problem.b, problem.X, problem.D
    containers = problem.containers

    yard = tuple_to_grid(state.yard_grid)
    ship = tuple_to_grid(state.ship_grid)

    found = False
    for r in range(a):
        for c in range(b):
            if yard[r][c] == container_id:
                ry, cy = r, c
                found = True
                break
        if found:
            break
    if not found:
        raise ValueError(f"Container {container_id} not found in yard in apply_action.")


    if ship[rs][cs] != 0:
        raise ValueError("Target ship cell is not empty in apply_action.")

    yard[ry][cy] = 0
    ship[rs][cs] = container_id

    left_cols, right_cols = get_left_right_columns(b)
    new_weight_left = state.weight_left
    new_weight_right = state.weight_right

    if cs in left_cols:
        new_weight_left += containers[container_id].weight
    else:
        new_weight_right += containers[container_id].weight

    load_c = loading_cost(X, ry, cy, rs, cs)
    dest_c = destination_penalty_for_position(cs, containers[container_id].destination, b, D)
    imb_c = imbalance_penalty(new_weight_left, new_weight_right)

    incremental = load_c + dest_c + imb_c

    new_state = State(
        yard_grid=grid_to_tuple(yard),
        ship_grid=grid_to_tuple(ship),
        weight_left=new_weight_left,
        weight_right=new_weight_right
    )

    return new_state, incremental


#HEURISTIC FOR A*
def admissible_heuristic(state: State, problem: ProblemSpec) -> float:
    a, b, X, D = problem.a, problem.b, problem.X, problem.D
    containers = problem.containers
    
    yard = tuple_to_grid(state.yard_grid)
    ship = tuple_to_grid(state.ship_grid)

    remaining = []
    for r in range(a):
        for c in range(b):
            cid = yard[r][c]
            if cid != 0:
                remaining.append((cid, r, c))

    empty_cells = []
    for r in range(a):
        for c in range(b):
            if ship[r][c] == 0:
                empty_cells.append((r, c))

    h_dist = 0.0
    h_dest = 0.0
    remaining_weight = 0

    if not empty_cells:
        empty_cells = []

    for cid, ry, cy in remaining:
        remaining_weight += containers[cid].weight

        min_dist = math.inf
        min_dest_pen = math.inf
        if empty_cells:
            for rs, cs in empty_cells:
                d = X + abs(ry - rs) + abs(cy - cs)
                if d < min_dist:
                    min_dist = d

                dest_pen = abs(ship_zone(cs, b, D) - containers[cid].destination)
                if dest_pen < min_dest_pen:
                    min_dest_pen = dest_pen
        else:
            min_dist = 0
            min_dest_pen = 0

        h_dist += min_dist
        h_dest += min_dest_pen

    current_imbalance = abs(state.weight_left - state.weight_right)
    h_bal = max(0, current_imbalance - remaining_weight)

    return h_dist + h_dest + h_bal



#A* SEARCH IMPLEMENTATION
@dataclass(order=True)
class PriorityNode:
    priority: float
    count: int
    state: State  # order=False fields below
    g: float
    parent: Optional['PriorityNode'] = None
    action: Optional[Tuple[int, int, int]] = None  # (container_id, rs, cs)


def astar_search(problem: ProblemSpec, start_state: State, weighted: float = 1.0, max_expansions: int = 1000000):

    start_time = time.time()
    h0 = admissible_heuristic(start_state, problem)
    start_node = PriorityNode(priority=h0, count=0, state=start_state, g=0.0, parent=None, action=None)

    open_heap = []
    entry_count = 0
    heapq.heappush(open_heap, (start_node.priority, entry_count, start_node))
    entry_count += 1

    closed: Dict[State, float] = {}
    nodes_expanded = 0

    while open_heap:
        _, _, node = heapq.heappop(open_heap)
        current_state = node.state
        current_g = node.g

        yard_flat = sum(sum(1 for cid in row if cid != 0) for row in tuple_to_grid(current_state.yard_grid))
        if yard_flat == 0:
            elapsed = time.time() - start_time
            actions = []
            path_states = []
            cur = node
            while cur and cur.action is not None:
                actions.append(cur.action)
                path_states.append(cur.state)
                cur = cur.parent
            actions.reverse()
            return node.state, actions, current_g, {'nodes_expanded': nodes_expanded, 'time': elapsed}

        if current_state in closed and closed[current_state] <= current_g:
            continue
        closed[current_state] = current_g

        nodes_expanded += 1
        if nodes_expanded > max_expansions:
            elapsed = time.time() - start_time
            return None, None, None, {'nodes_expanded': nodes_expanded, 'time': elapsed, 'terminated': 'max_expansions_reached'}

        yard = tuple_to_grid(current_state.yard_grid)
        ship = tuple_to_grid(current_state.ship_grid)
        a, b, D = problem.a, problem.b, problem.D

        remaining_ids = []
        for r in range(a):
            for c in range(b):
                cid = yard[r][c]
                if cid != 0:
                    remaining_ids.append(cid)

        empty_ship_cells = []
        for r in range(a):
            for c in range(b):
                if ship[r][c] == 0:
                    empty_ship_cells.append((r, c))


        if not empty_ship_cells and remaining_ids:
            continue

        for cid in remaining_ids:
            for (rs, cs) in empty_ship_cells:
                try:
                    succ_state, incr_cost = apply_action(current_state, problem, cid, rs, cs)
                except ValueError:
                    continue
                succ_g = current_g + incr_cost
                succ_h = admissible_heuristic(succ_state, problem)
                succ_f = succ_g + weighted * succ_h

                if succ_state in closed and closed[succ_state] <= succ_g:
                    continue

                new_node = PriorityNode(priority=succ_f, count=entry_count, state=succ_state, g=succ_g, parent=node, action=(cid, rs, cs))
                heapq.heappush(open_heap, (new_node.priority, entry_count, new_node))
                entry_count += 1

    elapsed = time.time() - start_time
    return None, None, None, {'nodes_expanded': nodes_expanded, 'time': elapsed, 'terminated': 'no_solution'}



# BEAM SEARCH IMPLEMENTATION
def beam_search(problem: ProblemSpec, start_state: State, beam_width: int = 10, max_expansions: int = 100000):
    start_time = time.time()
    
    current_beam = [(start_state, 0.0, None, None)]
    nodes_expanded = 0
    
    while current_beam and nodes_expanded < max_expansions:
        next_beam = []
        
        for state, g_cost, parent, action in current_beam:
            nodes_expanded += 1
            
            yard_flat = sum(sum(1 for cid in row if cid != 0) for row in tuple_to_grid(state.yard_grid))
            if yard_flat == 0:
                elapsed = time.time() - start_time
                
                actions = []
                current = (state, g_cost, parent, action)
                while current[3] is not None:  
                    actions.append(current[3])
                    current = current[2]  
                actions.reverse()
                
                return state, actions, g_cost, {'nodes_expanded': nodes_expanded, 'time': elapsed}
            
            yard = tuple_to_grid(state.yard_grid)
            ship = tuple_to_grid(state.ship_grid)
            a, b, D = problem.a, problem.b, problem.D
            
            remaining_ids = []
            for r in range(a):
                for c in range(b):
                    cid = yard[r][c]
                    if cid != 0:
                        remaining_ids.append(cid)
            
            empty_ship_cells = []
            for r in range(a):
                for c in range(b):
                    if ship[r][c] == 0:
                        empty_ship_cells.append((r, c))
            
            if not empty_ship_cells and remaining_ids:
                continue
            
            for cid in remaining_ids:
                cell_costs = []
                for (rs, cs) in empty_ship_cells:
                    try:
                        _, incr_cost = apply_action(state, problem, cid, rs, cs)
                        cell_costs.append(((rs, cs), incr_cost))
                    except ValueError:
                        continue
                
                cell_costs.sort(key=lambda x: x[1])
                for (rs, cs), _ in cell_costs[:2]:
                    try:
                        succ_state, incr_cost = apply_action(state, problem, cid, rs, cs)
                        succ_g = g_cost + incr_cost
                        succ_h = admissible_heuristic(succ_state, problem)
                        succ_f = succ_g + succ_h
                        
                        next_beam.append((succ_state, succ_g, (state, g_cost, parent, action), (cid, rs, cs), succ_f))
                    except ValueError:
                        continue
        

        next_beam.sort(key=lambda x: x[4])  
        current_beam = [(state, g, parent, action) for state, g, parent, action, f in next_beam[:beam_width]]
        
        if not current_beam:
            break
    
    elapsed = time.time() - start_time
    return None, None, None, {'nodes_expanded': nodes_expanded, 'time': elapsed, 'terminated': 'no_solution_or_max_expansions'}



def build_initial_state(problem: ProblemSpec, yard_layout: List[List[int]]) -> State:
    if len(yard_layout) != problem.a or any(len(row) != problem.b for row in yard_layout):
        raise ValueError("yard_layout dimensions do not match problem specification.")
    ship = [[0 for _ in range(problem.b)] for _ in range(problem.a)]

    weight_left = 0
    weight_right = 0

    return State(yard_grid=grid_to_tuple(yard_layout), ship_grid=grid_to_tuple(ship),
                 weight_left=weight_left, weight_right=weight_right)



#FUNCTION TO PRINT STATE(GENERATED BY CHATGPT)
def print_state(state: State, problem: ProblemSpec):
    yard = tuple_to_grid(state.yard_grid)
    ship = tuple_to_grid(state.ship_grid)
    print("YARD:")
    for r in range(problem.a):
        print(' '.join(f"{x:2d}" for x in yard[r]))
    print("SHIP:")
    for r in range(problem.a):
        print(' '.join(f"{x:2d}" for x in ship[r]))
    print(f"Weight Left: {state.weight_left}, Weight Right: {state.weight_right}, Imbalance: {abs(state.weight_left-state.weight_right)}")
    print("-" * 40)



def create_test_problem(a: int, b: int, X: int, num_containers: int, D: int = 3, seed: int = 42) -> Tuple[ProblemSpec, List[List[int]]]:
    """Create a test problem with specified parameters."""
    import random
    random.seed(seed)
    
    max_containers = a * b
    if num_containers > max_containers:
        raise ValueError(f"Cannot place {num_containers} containers in {a}x{b} grid")
    
    # Generate random container positions
    positions = []
    for r in range(a):
        for c in range(b):
            positions.append((r, c))
    
    selected_positions = random.sample(positions, num_containers)
    
    # Create containers with random weights and destinations
    containers = {}
    for i, (r, c) in enumerate(selected_positions, 1):
        weight = random.randint(5, 20)
        destination = random.randint(1, D)
        containers[i] = Container(id=i, weight=weight, destination=destination, position=(r, c))
    
    # Build yard layout
    yard_layout = [[0 for _ in range(b)] for _ in range(a)]
    for cid, cont in containers.items():
        ry, cy = cont.position
        yard_layout[ry][cy] = cid
    
    problem = ProblemSpec(a=a, b=b, X=X, containers=containers, D=D)
    return problem, yard_layout


def run_test():
    
    GRID_ROWS = 4           
    GRID_COLS = 6           
    SEPARATION_COST = 5
    NUM_DESTINATIONS = 3    
    

    CONTAINER_DATA = [
        (1, 10, 1, 0, 0),  
        (2, 15, 2, 0, 2),  
        (3, 8,  1, 1, 1),  
        (4, 12, 3, 1, 4),  
        (5, 6,  2, 2, 0),  
    ]
    

    # ALGORITHMS = ['beam']  
    ALGORITHMS = ['astar']
    # ALGORITHMS = ['astar', 'beam']  # Run both
    

    MAX_EXPANSIONS = 100000   
    BEAM_WIDTH = 10         

    

    

    containers = {}
    for cid, weight, destination, row, col in CONTAINER_DATA:
        containers[cid] = Container(id=cid, weight=weight, destination=destination, position=(row, col))
    
    yard_layout = [[0 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    for cid, cont in containers.items():
        ry, cy = cont.position
        if ry >= GRID_ROWS or cy >= GRID_COLS:
            raise ValueError(f"Container {cid} position ({ry},{cy}) is outside {GRID_ROWS}x{GRID_COLS} grid!")
        yard_layout[ry][cy] = cid
    
    problem = ProblemSpec(a=GRID_ROWS, b=GRID_COLS, X=SEPARATION_COST, containers=containers, D=NUM_DESTINATIONS)
    start_state = build_initial_state(problem, yard_layout)
    
    print(f"Problem: {GRID_ROWS}x{GRID_COLS} grid, {len(containers)} containers, X={SEPARATION_COST}, D={NUM_DESTINATIONS}")
    print("Containers defined:")
    for cid, cont in containers.items():
        print(f"  Container {cid}: weight={cont.weight}, dest={cont.destination}, position=({cont.position[0]},{cont.position[1]})")
    print()
    print("Initial State:")
    print_state(start_state, problem)
    
    results = {}
    
    # Run each selected algorithm
    for algo in ALGORITHMS:
        print(f"\n{'='*50}")
        print(f"Running {algo.upper()}...")
        print('='*50)
        
        if algo == 'astar':
            goal_state, actions, cost, stats = astar_search(
                problem, start_state, weighted=1.0, max_expansions=MAX_EXPANSIONS
            )
        elif algo == 'beam':
            goal_state, actions, cost, stats = beam_search(
                problem, start_state, beam_width=BEAM_WIDTH, max_expansions=MAX_EXPANSIONS
            )
        else:
            print(f"Unknown algorithm: {algo}")
            continue
        
        results[algo] = {
            'goal_state': goal_state,
            'actions': actions,
            'cost': cost,
            'stats': stats,
            'success': goal_state is not None
        }
        
        if goal_state is not None:
            print(f"✓ SUCCESS: Cost={cost:.2f}, Nodes Expanded={stats['nodes_expanded']}, Time={stats['time']:.2f}s")
            
            print("\nAction sequence:")
            for step, (cid, rs, cs) in enumerate(actions, 1):
                cont = problem.containers[cid]
                print(f"  {step:2d}. Container {cid} (weight={cont.weight}, dest={cont.destination}) -> ship[{rs},{cs}]")
            
            print(f"\nFinal state after {algo.upper()}:")
            print_state(goal_state, problem)
        else:
            print(f"✗ FAILED: {stats.get('terminated', 'unknown')}")
            print(f"  Nodes Expanded: {stats['nodes_expanded']}, Time: {stats['time']:.2f}s")
    
    # Summary comparison
    print(f"\n{'='*70}")
    print("SUMMARY COMPARISON")
    print('='*70)
    
    successful_results = {k: v for k, v in results.items() if v['success']}
    
    if successful_results:
        print(f"{'Algorithm':<15} {'Cost':<10} {'Nodes':<10} {'Time (s)':<10} {'Status'}")
        print('-' * 55)
        
        for algo in ALGORITHMS:
            if algo in results:
                r = results[algo]
                status = "SUCCESS" if r['success'] else "FAILED"
                cost_str = f"{r['cost']:.2f}" if r['success'] else "N/A"
                print(f"{algo.upper():<15} {cost_str:<10} {r['stats']['nodes_expanded']:<10} {r['stats']['time']:<10.2f} {status}")
        
        # Show best solution
        if len(successful_results) > 1:
            best_algo = min(successful_results.keys(), key=lambda k: successful_results[k]['cost'])
            print(f"\nBest overall solution: {best_algo.upper()} with cost {successful_results[best_algo]['cost']:.2f}")
        elif len(successful_results) == 1:
            best_algo = list(successful_results.keys())[0]
            print(f"\nOnly {best_algo.upper()} found a solution with cost {successful_results[best_algo]['cost']:.2f}")
    else:
        print("No algorithm found a solution. Try:")
        print("- Increasing MAX_EXPANSIONS")
        print("- Reducing NUM_CONTAINERS") 
        print("- Using smaller grid size")



if __name__ == "__main__":
    run_test()
