import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import readers
readers.ods_set_cell(sys.argv[1], sys.argv[3], sys.argv[4], sheet=sys.argv[2])
