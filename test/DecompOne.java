// Decompile the function at one address and print the result or the error (debugging aid).
// Script args: <hex address>
//@category Testing
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;

public class DecompOne extends GhidraScript {
	protected void run() throws Exception {
		ghidra.program.model.address.Address a = toAddr(Long.parseUnsignedLong(getScriptArgs()[0], 16));
		if (getFunctionAt(a) == null) {
			disassemble(a);
			createFunction(a, "f");
		}
		Function f = getFunctionAt(a);
		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		DecompileResults r = di.decompileFunction(f, 60, monitor);
		println("DECOMP completed=" + r.decompileCompleted() + " err=" + r.getErrorMessage());
		if (r.getDecompiledFunction() != null) {
			println("DECOMP C:\n" + r.getDecompiledFunction().getC());
		}
	}
}
