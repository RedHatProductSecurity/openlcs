from pelcd.tasks.test_tasks import add, mul, xsum


add_res = add.delay(4, 5)
assert add_res.get() == 9

mul_res = mul.delay(5, 6)
assert mul_res.get() == 30

xsum_res = xsum.delay([1, 2, 3, 4, 5, 6])
assert xsum_res.get() == 21
