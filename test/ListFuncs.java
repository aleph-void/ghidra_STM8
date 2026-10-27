//@category Testing
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class ListFuncs extends GhidraScript {
	protected void run() throws Exception {
		FunctionIterator fi = currentProgram.getFunctionManager().getFunctions(true);
		StringBuilder sb = new StringBuilder();
		while (fi.hasNext()) { Function f = fi.next(); sb.append(f.getName()+"@"+f.getEntryPoint()+"["+f.getBody().getNumAddresses()+"] "); }
		println("FUNCS: " + sb);
	}
}
