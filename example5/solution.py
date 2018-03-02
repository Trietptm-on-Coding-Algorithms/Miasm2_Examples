from miasm2.analysis.binary import Container
from miasm2.analysis.machine import Machine
from miasm2.analysis.sandbox import Sandbox_Linux_x86_64
from miasm2.core.asmbloc import *
from miasm2.expression.expression import *
cfg = AsmCFG()
block = None
data = []
index = 0

def stop(jitter):
	global data
	jitter.run = False
	data = [c for c in jitter.vm.get_mem(0x6022a0,0x6024a7-0x6022a0)]
	return True

def sub_template(label_name,size,line):
	global index
	global data
	if line == None:
		label = AsmLabel("%s"%label_name,offset=index)
	else:
		label = AsmLabel("%s %s"%(label_name,line),offset=index)
	blk = AsmBlock(AsmLabel("loc_%s"%index))
	blk.lines.append(label)
	index+=size
	return blk

def interpret():
	global data
	global block
	global index
	global cfg

	one_byte = lambda i: map(hex,map(ord,data[i+1]))
	four_byte = lambda i: map(hex,map(ord,data[i+1:i+5]))
	multi_byte = lambda i: map(hex,map(ord,data[i+1:i+16]))

	func_lst = {
		'f':("END",1,None),
		'g':("ADD",2,one_byte),
		'h':("SUB",2,one_byte),
		'i':("MUL",2,one_byte),
		'k':("INC",2,one_byte),
		'l':("DEC",2,one_byte),
		'm':("XOR",2,one_byte),
		'p':("PUSHD",5,four_byte),
		'q':("POP",2,one_byte),
		's':("MOVD",2,one_byte),
		'u':("LOOP",2,one_byte),
		'v':("CMP",2,one_byte),
		'w':("JL",2,one_byte),
		'x':("JG",2,one_byte),
		'y':("JZ",2,one_byte),
		'z':("INCD",1,None),
		'|':("FUN",16,multi_byte),
		'{':("DECD",1,None),
		'\xde':("NOP",1,None),
		'\xad':("NOP",1,None),
		'\xc0':("NOP",1,None),
		'\xde':("NOP",1,None),
	}

	blocks = {}

	while(index < len(data)):
		bcode = data[index]
		lst = func_lst.get(bcode,("",None))
		name = lst[0]
		size = lst[1]
		func = lst[2]

		if func == None:
			blk = sub_template(name,size,None)
		else:
			line = func(index)
			blk = sub_template(name,size,line)

		if block == None:
			block = blk
			cfg.add_node(block)
		else:
			n_block = blk
			cfg.add_node(n_block)
			cfg.add_edge(block,n_block,AsmConstraint.c_next)
			block = n_block
		blocks.update({block.lines[0].offset:block})

	for node in cfg._nodes:
		if "LOOP" in node.lines[0].name:
			offset = int(node.lines[-1].name.split(" ")[1].replace("[","").replace("]","").replace("'",""),16)
			offset = node.lines[-1].offset-offset
			cfg.add_edge(node,blocks[offset],AsmConstraint.c_to)
		if "J" in node.lines[0].name:
			offset = int(node.lines[-1].name.split(" ")[1].replace("[","").replace("]","").replace("'",""),16)
			offset= node.lines[-1].offset+offset+2
			cfg.add_edge(node,blocks[offset],AsmConstraint.c_to)
	
	i = 0
	s_blks = sorted(blocks)
	while(True):
		blk = blocks[s_blks[i]]
		if len(cfg.successors(blk)) == 1 and len(cfg.predecessors(blk)) == 1:
			try:
				pred = cfg.predecessors(blk)[0]
				if (len(cfg.successors(pred)) == 1 and len(cfg.predecessors(pred)) == 1) or (len(cfg.predecessors(pred)) == 0):
					succ = cfg.successors(blk)[0]
					pred.lines.append(blk.lines[0])
					if "END" not in blk.lines[0].name:
						cfg.add_edge(pred,succ,AsmConstraint.c_to)
					cfg.del_node(blk)
			except AssertionError:
				pass

		if i == s_blks.index(s_blks[-1]):
			break
		i+=1
def main():
	global cfg
	global block
	global data
	
	cont = Container.from_stream(open('300.bin'))
	bin_stream = cont.bin_stream
	adr = 0x401550
	machine = Machine(cont.arch)
	mdis = machine.dis_engine(bin_stream)
	blocks = mdis.dis_multibloc(adr)
	open("cfg_before.dot","w").write(blocks.dot())
	
	parser = Sandbox_Linux_x86_64.parser(description="300.bin")
	parser.add_argument("filename",help="filename")
	options = parser.parse_args()
	options.mimic_env = True
	
	sb = Sandbox_Linux_x86_64(options.filename,options,globals())
	sb.jitter.init_run(sb.entry_point)
	sb.jitter.add_breakpoint(sb.entry_point,stop)
	machine = Machine("x86_64")
	sb.run()
	interpret()
	open("vm_graph.dot","w").write(cfg.dot())
main()
