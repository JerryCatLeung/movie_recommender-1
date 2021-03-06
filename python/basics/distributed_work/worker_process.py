import multiprocessing, numpy, time


_cpu_count = multiprocessing.cpu_count()

_processes = [] # child processes
_pipes = [] # pipes to child processes

_process_data = {} # data to survive in between function calls



def _message_loop(conn):
    """
    :param conn: a multiprocessing.connection.PipeConnection
    """
    while True:
        request = conn.recv()
        op = request["op"]

        if op == "shutdown":
            return

        elif op == "set_data":
            for key in request:
                if key != "op":
                    _process_data[key] = request[key]

        elif op == "get_var":
            var_name = request["var_name"]
            conn.send(_process_data[var_name])

        elif op == "clear_all_data":
            _process_data.clear()

        elif op == "run_function":
            op_name = request["op_name"]

            if op_name in globals():
                globals()[op_name](request)
            else:
                print("Unhandled operation:", op)
                print("op_name:", op_name)
                # print("Request =", request) - request might be too large
        else:
            print("Unhandled operation:", op)
            # print("Request =", request) - request might be too large


def start_processes():
    """Spawns (cpu_count - 1) processes and pipes."""
    for i in range(0, _cpu_count - 1):
        pipe1, pipe2 = multiprocessing.Pipe()
        process = multiprocessing.Process(target = _message_loop,
                                          args=(pipe2,))
        process.start()
        _processes.append(process)
        _pipes.append(pipe1)


def end_processes():
    """Send "shutdown" message to all processes and wait for
    them to terminate."""
    for pipe in _pipes:
        pipe.send({"op": "shutdown"})

    for process in _processes:
        process.join()


def clear_all_data():
    for pipe in _pipes:
        pipe.send({"op": "clear_all_data"})

    _process_data.clear()


def split_list_and_send(data_list, start : int, length : int, var_name : str):
    """Split "data_list" and send it to each process. The
    current process gets the final split."""
    # compute split
    indices_and_lengths = _split(start, length, _cpu_count)

    # send to other processes
    for i in range(0, len(_pipes)):
        index = indices_and_lengths[i][0]
        length = indices_and_lengths[i][1]

        if length > 0:
            _pipes[i].send({
                "op": "set_data",
                var_name: data_list[index : index + length]
            })

    # the current process gets the final split
    index = indices_and_lengths[-1][0]
    length = indices_and_lengths[-1][1]
    _process_data[var_name] = data_list[index : index + length]


def run_function(function_name : str, arg_dict):
    """Run "function_name", with arg_dict being the
    argument dictionary."""
    if arg_dict is None:
        arg_dict = {}

    # The keys "op" and "op_name" will be over written - so these
    # should not be present in "arg_dict".
    if ("op" in arg_dict) or ("op_name" in arg_dict):
        raise Exception("run_function() cannot accept arg_dict with "
                        + 'keys "op" or "op_name".')

    # arg_dict is used as the request
    arg_dict["op"] = "run_function"
    arg_dict["op_name"] = function_name

    for pipe in _pipes:
        pipe.send(arg_dict)

    # for local process
    globals()[function_name](arg_dict)


def _split(start: int, length: int, num_splits: int):
    """Given a "start" and a "length", generate
    a list of (index, length) pairs. For example,
    (start=10, length=8, num_splits=4) generates
    [(10, 2), (12, 2), (14, 2), (16, 2)]."""

    if length >= num_splits:
        # standard case
        # compute the indices
        indices = []
        for i in range(0, num_splits):
            indices.append(start + int(length * i / num_splits))

        result = []
        # most of the lengths are (next index - current index)
        for i in range(0, len(indices) - 1):
            result.append((indices[i], indices[i+1] - indices[i]))

        # the length for the final index:
        final_length = start + length - indices[-1]
        result.append((indices[-1], final_length))

        return result

    else:
        # special case
        result = []
        index = start
        for i in range(0, num_splits):
            if index < start + length:
                result.append((index, 1))
                index += 1
            else:
                result.append((index, 0))

        return result


def concat_var_into_list(var_name : str):
    """Merge "var_name" in all processes and
    concatenate them into a single list."""
    for pipe in _pipes:
        pipe.send({
            "op": "get_var",
            "var_name": var_name
        })

    var_list = []
    for pipe in _pipes:
        var_list += pipe.recv()

    var_list += _process_data[var_name]
    return var_list


def concat_var_into_numpy_array(var_name : str):
    """Retrieve "var_name" from all processes and
    use numpy.concatenate(...) to combine them into
    a single numpy array."""
    for pipe in _pipes:
        pipe.send({
            "op": "get_var",
            "var_name": var_name
        })

    var_list = []
    for pipe in _pipes:
        var_list.append(pipe.recv())

    var_list.append(_process_data[var_name])
    return numpy.concatenate(var_list)


# End of framework
#####################################################################


def add(request):
    x1 = _process_data["x1"]
    x2 = _process_data["x2"]
    _process_data["sum"] = x1 + x2

    time.sleep(0.1 * len(x1))

