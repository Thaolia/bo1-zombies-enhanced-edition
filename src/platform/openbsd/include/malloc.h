#pragma once
// OpenBSD ships no <malloc.h>: the allocator is declared by <stdlib.h>. There is no malloc_usable_size either;
// msvc_intrinsics.h keeps an OpenBSD _aligned_* family that records the block size itself.
#include <stdlib.h>
