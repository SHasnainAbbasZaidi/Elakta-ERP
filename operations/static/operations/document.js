(() => {
  const form = document.getElementById('document-form');
  const body = document.getElementById('document-lines');
  const inventory = JSON.parse(document.getElementById('inventory-options').textContent);
  const taxes = JSON.parse(document.getElementById('tax-options').textContent);
  const round = n => Math.round((n + Number.EPSILON) * 100) / 100;
  const currency = n => 'PKR ' + n.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  const error = message => {const el=document.getElementById('document-error'); el.textContent=message; el.classList.toggle('d-none', !message);};
  function addLine(data = {}) {
    const row = document.createElement('tr');
    row.innerHTML = '<td><select name="inventory_item_id[]" aria-label="Inventory item" class="form-select"><option value="">Custom item</option></select></td><td><input name="item_name[]" aria-label="Item name" class="form-control" required><input name="description[]" aria-label="Description" placeholder="Description" class="form-control mt-1"></td><td><input name="qty[]" aria-label="Quantity" type="number" step="0.01" min="0.01" class="form-control" required></td><td><input name="unit[]" aria-label="Unit" class="form-control"></td><td><input name="unit_cost[]" aria-label="Unit cost" type="number" step="0.01" min="0" class="form-control" placeholder="Unknown"></td><td><input name="price[]" aria-label="Unit price" type="number" step="0.01" min="0" class="form-control" required></td><td><select name="item_tax[]" aria-label="Item tax" class="form-select"><option value="">None</option></select></td><td class="line-total"></td><td><button type="button" class="btn btn-outline-danger" aria-label="Remove item">×</button></td>';
    const field = name => row.querySelector(`[name="${name}[]"]`);
    inventory.forEach(item => field('inventory_item_id').add(new Option(`${item.category} · ${item.name}`, item.id)));
    taxes.forEach(tax => field('item_tax').add(new Option(`${tax.name} (${tax.rate}%)`, tax.id)));
    const values = {inventory_item_id:data.inventory_item_id??'', item_name:data.item_name??'', description:data.description??'', qty:data.qty??1, unit:data.unit??'', unit_cost:data.unit_cost??'', price:data.unit_price??0, item_tax:data.item_tax_id??''};
    Object.entries(values).forEach(([key,value]) => field(key).value=value);
    field('inventory_item_id').addEventListener('change', () => {
      const item = inventory.find(item => String(item.id) === field('inventory_item_id').value);
      if (item) {field('item_name').value=item.name; field('description').value=item.description; field('unit_cost').value=item.avg_unit_cost; field('unit').value=item.unit__name??'';}
      else field('unit_cost').value='';
      calculate();
    });
    row.querySelector('button').addEventListener('click', () => {row.remove(); calculate();});
    body.appendChild(row);
    calculate();
  }
  function calculate() {
    let subtotal=0, cost=0, taxTotal=0, missing=0;
    const mode = form.elements.tax_type.value;
    body.querySelectorAll('tr').forEach(row => {
      const value = name => row.querySelector(`[name="${name}[]"]`).value;
      const qty=Number(value('qty'))||0, price=Number(value('price'))||0;
      const base=round(qty*price);
      if (value('unit_cost')==='') missing++; else cost+=qty*(Number(value('unit_cost'))||0);
      const tax=taxes.find(t=>String(t.id)===value('item_tax'));
      const amount=mode==='Item' && tax ? round(base*Number(tax.rate)/100) : 0;
      row.querySelector('[name="item_tax[]"]').disabled=mode!=='Item';
      row.querySelector('.line-total').textContent=currency(base+amount);
      subtotal+=base; taxTotal+=amount;
    });
    const discount=Number(form.elements.discount.value)||0;
    const net=round(subtotal-discount);
    const global=taxes.find(t=>String(t.id)===form.elements.global_tax.value);
    form.elements.global_tax.disabled=mode!=='Global';
    if(mode==='Global') taxTotal=global?round(Math.max(0,net)*Number(global.rate)/100):0;
    cost=round(cost);
    const complete=!missing && body.children.length>0;
    document.getElementById('document-subtotal').textContent=currency(subtotal);
    document.getElementById('document-net').textContent=currency(net);
    document.getElementById('document-tax').textContent=currency(taxTotal);
    document.getElementById('document-total').textContent=currency(net+taxTotal);
    document.getElementById('document-cost').textContent=currency(cost)+(missing?' (known costs only)':'');
    document.getElementById('document-profit').textContent=complete?currency(net-cost):'Incomplete costs';
    document.getElementById('document-margin').textContent=complete && net>0?((net-cost)/net*100).toFixed(2)+'%':'—';
  }
  form.addEventListener('input', calculate); form.addEventListener('change', calculate);
  form.addEventListener('submit', event => {if(!body.children.length){event.preventDefault();error('Add at least one item.');}});
  document.getElementById('add-document-line').addEventListener('click',()=>addLine());
  document.getElementById('load-document').addEventListener('click', async () => {
    const url=document.getElementById('copy-document').value;if(!url)return;
    try {const response=await fetch(url);if(!response.ok)throw Error();const data=await response.json();body.replaceChildren();data.items.forEach(addLine);error('');}
    catch(_){error('Could not load document items. Please try again.');}
  });
  const initial=JSON.parse(document.getElementById('initial-lines').textContent);
  (initial.length?initial:[{}]).forEach(addLine);
})();
